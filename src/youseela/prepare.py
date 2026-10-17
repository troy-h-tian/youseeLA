"""Assemble real source inputs without pretending absent imagery is available."""

from datetime import date
from typing import Any

from youseela.contracts import AreaInput, Dataset, Evidence, NumericalIndicators
from youseela.features import affordability_pressure, rent_burden_share, renter_share


def prepare_dataset(geography: dict[str, Any], latest: dict[str, dict[str, Any]],
                    prior: dict[str, dict[str, Any]], latest_year: int, prior_year: int,
                    area_ids: list[str] | None = None, geography_verified: bool = False) -> Dataset:
    if prior_year >= latest_year:
        raise ValueError("Prior Census period must precede latest period")
    areas: list[AreaInput] = []
    evidence: list[Evidence] = []
    available = {str(f["properties"]["GEOID"]): f for f in geography["features"]}
    chosen = area_ids or sorted(available)
    if any(geoid not in available for geoid in chosen):
        raise ValueError("Requested tract is not in the verified geographic inventory")
    for geoid in chosen:
        now, before = latest.get(geoid, {}), prior.get(geoid, {})
        pressure = affordability_pressure(before, now)
        refs: list[str] = []
        for year, row in [(latest_year, now), (prior_year, before)]:
            if row:
                evidence_id = f"acs-{year}-{geoid}"
                refs.append(evidence_id)
                evidence.append(Evidence(id=evidence_id, area_id=geoid, kind="census", mode="both",
                                         source_url=f"https://api.census.gov/data/{year}/acs/acs5.html",
                                         source_date=date(year,12,31), attribution="U.S. Census Bureau, American Community Survey",
                                         license="U.S. government data", reviewed=True,
                                         note=f"Pooled {year-4}–{year} estimates; source_date is period end. GEOID {geoid}. Automated ratio/schema checks; raw rows retained separately."))
        warnings = [pressure.reason, "ACS windows may overlap; bounds are sensitivity bounds, not a hypothesis test."]
        if not geography_verified:
            warnings.append("Tract comparability across source vintages has not been verified; change score withheld.")
        areas.append(AreaInput(id=geoid, name=str(now.get("NAME", f"Census tract {geoid}")),
                               geometry=available[geoid]["geometry"],
                               boundary_source_url=geography.get("source"), boundary_vintage=geography.get("boundary_vintage"),
                               indicators=NumericalIndicators(rent_burden_share=rent_burden_share(now), renter_share=renter_share(now),
                                                              affordability_pressure=pressure.value if geography_verified else None,
                                                              periods=[f"{prior_year-4}–{prior_year}", f"{latest_year-4}–{latest_year}"],
                                                              evidence_ids=refs, warnings=warnings)))
    return Dataset(data_kind="real", areas=areas, evidence=evidence)
