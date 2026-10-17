"""Non-image neighborhood-change context and an external benchmark. Nothing here changes a score."""

import json
import statistics
from collections.abc import Callable
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import Field
from shapely.geometry import shape
from shapely.ops import unary_union

from youseela.contracts import ContextIndicator, Dataset, Evidence, Record, ReferenceTypology
from youseela.sources import assessor, business, typology

MINIMUM_PARCELS = 50
LA_COUNTY_TERMS = "Los Angeles County open data; see https://data.lacounty.gov terms of use"


class AreaContext(Record):
    context: list[ContextIndicator] = Field(default_factory=list)
    reference_typology: ReferenceTypology | None = None


class ContextFile(Record):
    generated_at: datetime
    sources: dict[str, Any]
    areas: dict[str, AreaContext]
    evidence: list[Evidence]


def typology_context(area_ids: list[str], udp: dict[str, str],
                     relationship: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, ReferenceTypology], list[Evidence]]:
    labels: dict[str, ReferenceTypology] = {}
    evidence: list[Evidence] = []
    for geoid in area_ids:
        tract10 = typology.equivalent_2010_tract(geoid, relationship)
        code = udp.get(tract10) if tract10 else None
        if not tract10 or not code:
            continue
        evidence_id = f"udp-2018-{geoid}"
        evidence.append(Evidence(id=evidence_id, area_id=geoid, kind="typology", mode="both", source_url=typology.UDP_PAGE,
                                 source_date=date(2018, 12, 31), reviewed=True,
                                 attribution="Urban Displacement Project, Los Angeles displacement typology",
                                 license="GPL-3.0 (source repository)",
                                 note=f"2010 tract {tract10} matched to 2020 tract {geoid} by Census land-area relationship (at least 95% mutual overlap). "
                                      f"Based on ACS 2014–2018; predates SoFi Stadium's 2020 opening. Pinned commit {typology.UDP_COMMIT[:12]}."))
        labels[geoid] = ReferenceTypology(code=code, label=typology.LABELS[code], source_period="ACS 2014–2018",
                                          source_tract=tract10, evidence_id=evidence_id)
    return labels, evidence


def share(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator >= MINIMUM_PARCELS else None


def assessor_context(counts: dict[str, dict[str, int]], roll_year: int, suffix: str) -> tuple[dict[str, list[ContextIndicator]], list[Evidence]]:
    first = roll_year - assessor.WINDOW_YEARS + 1
    period = f"Base years {first}–{roll_year} ({roll_year} roll)"
    indicators: dict[str, list[ContextIndicator]] = {}
    evidence: list[Evidence] = []
    for geoid, tally in counts.items():
        if tally["taxable"] == 0:
            continue
        evidence_id = f"assessor-{roll_year}-{geoid}"
        evidence.append(Evidence(id=evidence_id, area_id=geoid, kind="assessor", mode="both",
                                 source_url=assessor.service_url(roll_year).removesuffix("/query"),
                                 source_date=date(roll_year, 1, 1), reviewed=True,
                                 attribution="Los Angeles County Office of the Assessor, secured assessment roll",
                                 license=LA_COUNTY_TERMS,
                                 note=f"{tally['taxable']} taxable parcels located by parcel centroid. Automated aggregation; parcel rows retained separately."))
        small = f"Fewer than {MINIMUM_PARCELS} taxable parcels; share withheld." if tally["taxable"] < MINIMUM_PARCELS else ""
        indicators[geoid] = [
            ContextIndicator(key=f"reassessed_share_{suffix}", label="Taxable parcels reassessed after a sale or new construction",
                             value=share(tally["reassessed"], tally["taxable"]), unit="share", period=period, evidence_ids=[evidence_id],
                             note=small or f"{tally['reassessed']}/{tally['taxable']} parcels. Prop 13 base years reset on market sales and new construction, not on most family transfers."),
            ContextIndicator(key=f"built_or_renovated_share_{suffix}", label="Taxable parcels built or substantially renovated",
                             value=share(tally["built_or_renovated"], tally["taxable"]), unit="share", period=f"Effective year built {first}–{roll_year}",
                             evidence_ids=[evidence_id],
                             note=small or f"{tally['built_or_renovated']}/{tally['taxable']} parcels by the Assessor's effective year built, which reflects major renovation as well as new construction."),
        ]
    return indicators, evidence


def business_context(zcta_map: dict[str, tuple[str, float]], counts: dict[str, dict[str, int]],
                     year: int, suffix: str) -> tuple[dict[str, list[ContextIndicator]], list[Evidence]]:
    indicators: dict[str, list[ContextIndicator]] = {}
    evidence: list[Evidence] = []
    for geoid, (zcta, coverage) in zcta_map.items():
        if zcta not in counts:
            continue
        evidence_id = f"zbp-{year}-{geoid}"
        evidence.append(Evidence(id=evidence_id, area_id=geoid, kind="business_patterns", mode="commercial",
                                 source_url=business.zbp_url(year), source_date=date(year, 12, 31), reviewed=True,
                                 attribution="U.S. Census Bureau, ZIP Code Business Patterns", license="U.S. government data",
                                 note=f"ZIP {zcta} covers {coverage:.0%} of this tract (2020 ZCTA approximation of the ZIP). Counts describe the whole ZIP, not the tract."))
        indicators[geoid] = [ContextIndicator(
            key=f"amenity_establishments_{suffix}", label=f"Cafes, sit-down restaurants, bars and groceries in ZIP {zcta}",
            value=business.amenity_count(counts[zcta]), unit="count", period=str(year), evidence_ids=[evidence_id],
            note=f"ZIP-level count shared by every tract mostly inside {zcta}. Categories follow Glaeser, Kim & Luca's gentrification-linked business types; establishment counts, not openings.")]
    return indicators, evidence


def benchmark(areas: dict[str, AreaContext]) -> dict[str, Any]:
    """Summarize each context indicator within UDP groups. Descriptive only; no accuracy is claimed."""
    groups: dict[str, dict[str, list[float]]] = {}
    for item in areas.values():
        if not item.reference_typology:
            continue
        values = groups.setdefault(item.reference_typology.code, {})
        by_key = {c.key: c.value for c in item.context}
        for key, value in by_key.items():
            if value is not None:
                values.setdefault(key, []).append(value)
        prior, latest = by_key.get("reassessed_share_prior"), by_key.get("reassessed_share_latest")
        if prior is not None and latest is not None:
            values.setdefault("reassessed_share_change", []).append(latest - prior)
    return {
        "reference": "Urban Displacement Project Los Angeles typology (ACS 2014–2018)",
        "tracts_with_reference": sum(1 for item in areas.values() if item.reference_typology),
        "tracts_without_reference": sorted(k for k, item in areas.items() if not item.reference_typology),
        "groups": {code: {"label": typology.LABELS[code], "tracts": max((len(v) for v in values.values()), default=0),
                          "medians": {key: round(statistics.median(v), 4) for key, v in sorted(values.items())},
                          "counts": {key: len(v) for key, v in sorted(values.items())}}
                   for code, values in sorted(groups.items())},
        "limitations": [
            "UDP is itself a model built from Census data, not observed displacement; it is a reference point, not ground truth.",
            "The UDP period (2014–2018) predates SoFi Stadium's opening and the assessor/business windows compared here.",
            "Few tracts per group; medians are descriptive and no statistical test or accuracy figure is implied.",
            "Business counts are ZIP-level and repeated across tracts in the same ZIP.",
            "No Inglewood tract is classified as gentrifying by UDP, so these data cannot validate gentrification detection directly.",
        ],
    }


def cached_json(path: Path, fetch: Callable[[], Any]) -> Any:
    if path.exists():
        return json.loads(path.read_text())
    value = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def cached_text(path: Path, url: str) -> str:
    if path.exists():
        return path.read_text()
    text = typology.fetch_text(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return text


def collect(geography: dict[str, Any], raw: Path, prior_roll: int, latest_roll: int,
            prior_zbp: int, latest_zbp: int) -> ContextFile:
    """Fetch (or reuse cached) raw sources under `raw` and derive per-tract context."""
    if prior_roll + assessor.WINDOW_YEARS > latest_roll:
        raise ValueError("Assessor roll windows must not overlap; use rolls at least five years apart")
    if prior_zbp >= latest_zbp:
        raise ValueError("Prior business-patterns year must precede the latest year")
    areas = {str(f["properties"]["GEOID"]): f["geometry"] for f in geography["features"]}
    bounds = unary_union([shape(g) for g in areas.values()]).bounds
    udp = typology.parse_udp(cached_text(raw/"udp-los-angeles.csv", typology.UDP_URL))
    relationship = typology.parse_relationship(cached_text(raw/"tract20-tract10-ca.txt", typology.RELATIONSHIP_URL))
    labels, evidence = typology_context(sorted(areas), udp, relationship)
    indicators: dict[str, list[ContextIndicator]] = {geoid: [] for geoid in areas}
    for roll, suffix in [(prior_roll, "prior"), (latest_roll, "latest")]:
        parcels = cached_json(raw/f"assessor-{roll}.json", lambda roll=roll: assessor.fetch_parcels(roll, bounds))
        found, records = assessor_context(assessor.tract_activity(parcels, areas, roll), roll, suffix)
        evidence.extend(records)
        for geoid, items in found.items():
            indicators[geoid].extend(items)
    zctas = cached_json(raw/"zcta-2020.json", lambda: business.fetch_zctas(bounds))
    zcta_map = business.dominant_zctas(areas, zctas)
    for year, suffix in [(prior_zbp, "prior"), (latest_zbp, "latest")]:
        counts = business.read_zbp(business.download_zbp(year, raw/f"zbp{year}.zip"), {z for z, _ in zcta_map.values()})
        found, records = business_context(zcta_map, counts, year, suffix)
        evidence.extend(records)
        for geoid, items in found.items():
            indicators[geoid].extend(items)
    return ContextFile(generated_at=datetime.now(timezone.utc),
                       sources={"udp": typology.UDP_URL, "tract_relationship": typology.RELATIONSHIP_URL,
                                "assessor_rolls": [prior_roll, latest_roll], "business_patterns_years": [prior_zbp, latest_zbp],
                                "amenity_naics": business.AMENITY_NAICS, "minimum_parcels": MINIMUM_PARCELS},
                       areas={geoid: AreaContext(context=indicators[geoid], reference_typology=labels.get(geoid)) for geoid in sorted(areas)},
                       evidence=evidence)


def attach(dataset: Dataset, context: ContextFile, as_of: date) -> Dataset:
    """Add context to matching areas, keeping only sources dated on or before `as_of`. Scoring ignores these fields."""
    result = dataset.model_copy(deep=True)
    selected = {area.id for area in result.areas}
    existing = {e.id for e in result.evidence}
    # A historical assessment must not cite sources from after its own date.
    dated = {e.id: e for e in context.evidence if e.area_id in selected and e.source_date <= as_of}
    for area in result.areas:
        if area.id in context.areas:
            item = context.areas[area.id]
            area.context = [c for c in item.context if all(ref in dated for ref in c.evidence_ids)]
            typology_ref = item.reference_typology
            area.reference_typology = typology_ref if typology_ref and typology_ref.evidence_id in dated else None
    result.evidence.extend(e for e in dated.values() if e.id not in existing)
    return result
