"""Countywide check: do assessor indicators separate UDP-gentrifying from low-income non-gentrifying tracts?"""

import argparse
import json
import math
import random
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import Point, shape

from youseela.sources import assessor, typology
from youseela.sources.geography import query_layer

GENTRIFYING = {"EOG", "AdvG"}
COMPARISON = {"LISD"}
RESIDENTIAL = {"SFR", "CND", "R-I"}
FIELDS = ["AIN", "RollYear", "isTaxableParcel", "Roll_LandBaseYear", "EffectiveYearBuilt", "UseType",
          "SQFTmain", "Roll_totLandImp", "CENTER_LAT", "CENTER_LON"]
MINIMUM_SALES = 10


def sample_tracts(udp: dict[str, str], exclude: set[str], per_group: int, seed: int) -> dict[str, str]:
    """Return GEOID -> 'gentrifying' or 'comparison' for a seeded random sample of LA County tracts."""
    rng = random.Random(seed)
    county = {g: code for g, code in udp.items() if g.startswith("06037") and g not in exclude}
    chosen: dict[str, str] = {}
    for name, codes in [("gentrifying", GENTRIFYING), ("comparison", COMPARISON)]:
        pool = sorted(g for g, code in county.items() if code in codes)
        if len(pool) < per_group:
            raise ValueError(f"Only {len(pool)} {name} tracts are available")
        chosen.update({g: name for g in rng.sample(pool, per_group)})
    return chosen


def tract_metrics(parcels: list[dict[str, Any]], geometry: dict[str, Any], roll_year: int) -> dict[str, Any]:
    polygon = shape(geometry)
    first = roll_year - assessor.WINDOW_YEARS + 1
    seen: set[str] = set()
    taxable = reassessed = built = 0
    values: list[float] = []
    for parcel in parcels:
        ain, lat, lon = str(parcel.get("AIN", "")), parcel.get("CENTER_LAT"), parcel.get("CENTER_LON")
        if (str(parcel.get("RollYear")) != str(roll_year) or parcel.get("isTaxableParcel") != "Y" or not ain or ain in seen
                or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not polygon.covers(Point(lon, lat))):
            continue
        seen.add(ain)
        taxable += 1
        base, effective = assessor.year(parcel.get("Roll_LandBaseYear")), assessor.year(parcel.get("EffectiveYearBuilt"))
        recent = base is not None and first <= base <= roll_year
        reassessed += recent
        built += effective is not None and first <= effective <= roll_year
        sqft, value = parcel.get("SQFTmain") or 0, parcel.get("Roll_totLandImp") or 0
        # A recent base year means the assessed value is close to a recent market price.
        if recent and parcel.get("UseType") in RESIDENTIAL and sqft >= 300 and value > 0:
            values.append(value / sqft)
    enough = taxable >= 50
    return {"taxable": taxable,
            "reassessed_share": reassessed / taxable if enough else None,
            "built_or_renovated_share": built / taxable if enough else None,
            "recent_sales": len(values),
            "recent_sale_value_per_sqft": statistics.median(values) if len(values) >= MINIMUM_SALES else None}


def indicators(early: dict[str, Any], late: dict[str, Any]) -> dict[str, float | None]:
    def diff(key: str) -> float | None:
        return late[key] - early[key] if late[key] is not None and early[key] is not None else None
    a, b = early["recent_sale_value_per_sqft"], late["recent_sale_value_per_sqft"]
    return {"reassessed_share": late["reassessed_share"], "reassessed_share_change": diff("reassessed_share"),
            "built_or_renovated_share": late["built_or_renovated_share"],
            "built_or_renovated_share_change": diff("built_or_renovated_share"),
            "recent_sale_value_growth": math.log(b / a) if a and b else None}


def auc(positive: list[float], negative: list[float]) -> float:
    """Probability a random gentrifying tract scores higher than a random comparison tract (ties count half)."""
    wins = sum((p > n) + .5 * (p == n) for p in positive for n in negative)
    return wins / (len(positive) * len(negative))


def bootstrap_interval(positive: list[float], negative: list[float], seed: int, rounds: int = 2000) -> list[float]:
    rng = random.Random(seed)
    draws = sorted(auc(rng.choices(positive, k=len(positive)), rng.choices(negative, k=len(negative))) for _ in range(rounds))
    return [round(draws[int(.025 * rounds)], 3), round(draws[int(.975 * rounds) - 1], 3)]


def compare(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    result = {}
    for key in ["reassessed_share", "reassessed_share_change", "built_or_renovated_share",
                "built_or_renovated_share_change", "recent_sale_value_growth"]:
        positive = [r["indicators"][key] for r in rows if r["group"] == "gentrifying" and r["indicators"][key] is not None]
        negative = [r["indicators"][key] for r in rows if r["group"] == "comparison" and r["indicators"][key] is not None]
        if len(positive) < 10 or len(negative) < 10:
            result[key] = {"auc": None, "reason": "Fewer than ten tracts with values in a group"}
            continue
        result[key] = {"auc": round(auc(positive, negative), 3), "auc_95_bootstrap": bootstrap_interval(positive, negative, seed),
                       "gentrifying": {"n": len(positive), "median": round(statistics.median(positive), 4)},
                       "comparison": {"n": len(negative), "median": round(statistics.median(negative), 4)}}
    result["recent_sale_value_growth"]["circularity"] = (
        "UDP's gentrification definition includes home-value and rent increases, so price growth is expected to "
        "separate the groups partly by construction. Treat this as a sanity check, not independent validation.")
    return result


def fetch_geometries(geoids: list[str], client: httpx.Client) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for start in range(0, len(geoids), 40):
        chunk = geoids[start:start + 40]
        where = "GEOID IN (" + ",".join(f"'{g}'" for g in chunk) + ")"
        for feature in query_layer("tigerWMS_Census2010", 14, where, client)["features"]:
            result[str(feature["properties"]["GEOID"])] = feature["geometry"]
    return result


def cached_parcels(path: Path, roll: int, geometry: dict[str, Any], client: httpx.Client) -> list[dict[str, Any]]:
    if path.exists():
        return json.loads(path.read_text())
    parcels = assessor.fetch_parcels(roll, shape(geometry).bounds, client=client, fields=FIELDS)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(parcels))
    temporary.replace(path)
    return parcels


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-group", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20261017)
    parser.add_argument("--early-roll", type=int, default=2013)
    parser.add_argument("--late-roll", type=int, default=2018)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--geography", type=Path, default=Path("data/curated/areas.geojson"))
    parser.add_argument("--raw", type=Path, default=Path("data/raw/context"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/context-validation.json"))
    args = parser.parse_args()
    if args.early_roll + assessor.WINDOW_YEARS > args.late_roll:
        raise SystemExit("Assessor windows must not overlap")
    udp = typology.parse_udp((args.raw / "udp-los-angeles.csv").read_text())
    exclude = {str(f["properties"]["GEOID"]) for f in json.loads(args.geography.read_text())["features"]}
    sample = sample_tracts(udp, exclude, args.per_group, args.seed)
    with httpx.Client(timeout=180) as client:
        geometries = fetch_geometries(sorted(sample), client)
        jobs = {(roll, g): args.raw / "validation" / f"{roll}-{g}.json" for g in geometries for roll in (args.early_roll, args.late_roll)}
        parcels: dict[tuple[int, str], list[dict[str, Any]]] = {}
        failed: dict[str, str] = {}
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(cached_parcels, path, roll, geometries[g], client): (roll, g) for (roll, g), path in jobs.items()}
            for done, future in enumerate(as_completed(futures), 1):
                roll, g = futures[future]
                try:
                    parcels[(roll, g)] = future.result()
                except ValueError as error:
                    failed[g] = str(error)
                if done % 20 == 0 or done == len(futures):
                    print(f"{done}/{len(futures)} tract-roll queries complete ({len(failed)} tracts failed)", flush=True)
    rows = []
    for g in sorted(geometries):
        if g in failed:
            continue
        early = tract_metrics(parcels[(args.early_roll, g)], geometries[g], args.early_roll)
        late = tract_metrics(parcels[(args.late_roll, g)], geometries[g], args.late_roll)
        rows.append({"geoid": g, "group": sample[g], "udp": udp[g], "taxable_parcels": late["taxable"],
                     "recent_sales": [early["recent_sales"], late["recent_sales"]], "indicators": indicators(early, late)})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "protocol": "udp-county-assessor-v1",
        "question": "Do assessor indicators rank UDP-gentrifying tracts above low-income non-gentrifying tracts?",
        "groups": {"gentrifying": sorted(GENTRIFYING), "comparison": sorted(COMPARISON)},
        "reference": f"UDP Los Angeles typology, ACS 2014–2018, commit {typology.UDP_COMMIT}",
        "windows": {"early": f"Base years {args.early_roll - 4}–{args.early_roll}", "late": f"Base years {args.late_roll - 4}–{args.late_roll}"},
        "seed": args.seed, "sampled": {name: sum(v == name for v in sample.values()) for name in ("gentrifying", "comparison")},
        "missing_geometry": sorted(set(sample) - set(geometries)), "failed_queries": failed, "tracts_analyzed": len(rows),
        "results": compare(rows, args.seed),
        "interpretation": "AUC 0.5 means no separation; 1.0 means every gentrifying tract ranks above every comparison tract.",
        "limitations": ["UDP is a Census-based classification, not observed displacement.",
                        "Comparison tracts are low-income tracts UDP did not classify as gentrifying; results do not cover other typologies.",
                        "Inglewood tracts are excluded; countywide separation does not guarantee the same behavior there.",
                        "The 2009–2013 window includes foreclosure-driven sales, which affects change measures."],
        "tracts": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    summary = ", ".join(f"{k} AUC {v['auc']}" for k, v in report["results"].items() if v.get("auc") is not None)
    print(f"Analyzed {len(rows)} tracts: {summary}. Saved {args.output}")


if __name__ == "__main__":
    main()
