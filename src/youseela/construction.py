"""Find before/after street photos of known new construction, located from the Assessor roll."""

import argparse
import json
import os
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from shapely.geometry import Point, shape

from youseela.sources import assessor
from youseela.sources.imagery import bearing_and_distance, discover_images, pair_candidates, target_bbox


def construction_sites(parcels: list[dict[str, Any]], geometry: dict[str, Any], first_year: int, last_year: int,
                       roll_year: int, min_parcels: int = 1) -> list[dict[str, Any]]:
    """Group taxable parcels built or rebuilt in [first_year, last_year] by Assessor map book and page."""
    polygon = shape(geometry)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for parcel in parcels:
        ain, lat, lon = str(parcel.get("AIN", "")), parcel.get("CENTER_LAT"), parcel.get("CENTER_LON")
        built = assessor.year(parcel.get("EffectiveYearBuilt"))
        if (str(parcel.get("RollYear")) != str(roll_year) or parcel.get("isTaxableParcel") != "Y" or len(ain) != 10
                or ain in seen or built is None or not first_year <= built <= last_year
                or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)) or not polygon.covers(Point(lon, lat))):
            continue
        seen.add(ain)
        groups[ain[:7]].append(parcel)
    sites = []
    for page, members in groups.items():
        if len(members) < min_parcels:
            continue
        lon = sum(p["CENTER_LON"] for p in members) / len(members)
        lat = sum(p["CENTER_LAT"] for p in members) / len(members)
        extent = max(bearing_and_distance((lon, lat), (p["CENTER_LON"], p["CENTER_LAT"]))[1] for p in members)
        years = sorted({assessor.year(p["EffectiveYearBuilt"]) for p in members})
        sites.append({"site_id": f"assessor-page-{page}", "parcels": len(members), "years_built": years,
                      "longitude": round(lon, 6), "latitude": round(lat, 6), "extent_m": round(extent, 1)})
    return sorted(sites, key=lambda s: -s["parcels"])


def public_image(item: dict[str, Any]) -> dict[str, Any]:
    """Keep reproducible metadata only; Mapillary thumbnail URLs are signed and expire."""
    keys = ["id", "captured_at", "compass_angle", "computed_compass_angle", "is_pano",
            "target_distance_m", "target_bearing", "heading_offset"]
    return {**{k: item.get(k) for k in keys}, "creator": (item.get("creator") or {}).get("username"),
            "url": f"https://www.mapillary.com/app/?pKey={item['id']}"}


def search_site(site: dict[str, Any], token: str, before: date, after: date, client: httpx.Client,
                margin_m: float = 40, max_heading_offset: float = 60) -> dict[str, Any]:
    target = (site["longitude"], site["latitude"])
    bbox = target_bbox(target, min(site["extent_m"] + margin_m, 550))
    common = dict(client=client, limit=100, max_pages=5, target=target, max_heading_offset=max_heading_offset)
    earlier = discover_images(bbox, token, captured_before=before, **common)
    later = discover_images(bbox, token, captured_after=after, **common)
    pairs = pair_candidates(earlier["images"], later["images"])
    return {**site, "search_bbox": [round(v, 6) for v in bbox],
            "earlier": {"captured_before": before.isoformat(), "count": len(earlier["images"]), "has_more": earlier["has_more"],
                        "images": [public_image(i) for i in earlier["images"]]},
            "later": {"captured_after": after.isoformat(), "count": len(later["images"]), "has_more": later["has_more"],
                      "images": [public_image(i) for i in later["images"]]},
            "pairs": pairs[:20], "pair_count": len(pairs)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tract", default="06037601001")
    parser.add_argument("--geography", type=Path, default=Path("data/curated/areas.geojson"))
    parser.add_argument("--roll", type=Path, default=Path("data/raw/context/assessor-2025.json"))
    parser.add_argument("--roll-year", type=int, default=2025)
    parser.add_argument("--built-from", type=int, default=2019)
    parser.add_argument("--built-to", type=int, default=2025)
    parser.add_argument("--before", type=date.fromisoformat, default=date(2019, 1, 1))
    parser.add_argument("--after", type=date.fromisoformat, default=date(2023, 1, 1))
    parser.add_argument("--output", type=Path, default=Path("artifacts/construction-pairs.json"))
    args = parser.parse_args()
    load_dotenv(override=False)
    areas = {str(f["properties"]["GEOID"]): f["geometry"] for f in json.loads(args.geography.read_text())["features"]}
    if args.tract not in areas:
        raise SystemExit(f"Tract {args.tract} is not in {args.geography}")
    sites = construction_sites(json.loads(args.roll.read_text()), areas[args.tract], args.built_from, args.built_to, args.roll_year)
    token = os.environ.get("MAPILLARY_ACCESS_TOKEN", "")
    results = []
    with httpx.Client(timeout=30) as client:
        for site in sites:
            try:
                results.append(search_site(site, token, args.before, args.after, client))
            except ValueError as error:
                results.append({**site, "error": str(error)})
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "tract": args.tract,
              "source": "LA County Assessor roll effective year built; Mapillary images (CC BY-SA 4.0)",
              "built_years": [args.built_from, args.built_to], "sites": results,
              "rule": "Pairs: same spot (<=15 m) and direction (<=30 degrees), at least one year apart, camera facing the site (<=60 degrees).",
              "limitations": ["A matching pair shows the same viewpoint, not necessarily the construction itself; inspect every pair.",
                              "Effective year built includes major renovation, not only new buildings.",
                              "Zero pairs means none in the bounded Mapillary search, not that no imagery exists anywhere."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    for item in results:
        print(f"{item['site_id']}: {item['parcels']} parcels built {item['years_built']}; "
              + (f"error: {item['error']}" if "error" in item else
                 f"{item['earlier']['count']} earlier, {item['later']['count']} later facing images, {item['pair_count']} pairs"))
    print(f"Saved {args.output}")


if __name__ == "__main__":
    main()
