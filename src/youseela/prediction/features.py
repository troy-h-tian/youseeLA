"""Tract feature tables and five-year rent-pressure labels for LA County."""

import math
import statistics
from dataclasses import dataclass
from typing import Any, Mapping

from youseela.features import number, rent_burden_share, renter_share
from youseela.sources import business

# (key, label used in explanations, group). Groups drive the ablation study.
FEATURES: list[tuple[str, str, str]] = [
    ("log_population", "Population (log)", "census"),
    ("income_vs_county", "Median household income relative to county", "census"),
    ("rent_vs_county", "Median rent relative to county", "census"),
    ("home_value_vs_county", "Median home value relative to county", "census"),
    ("rent_income_pct", "Median rent as % of income", "census"),
    ("rent_burden", "Renters paying 30%+ of income on rent", "census"),
    ("renter_share", "Renter share of households", "census"),
    ("bachelor_share", "Adults with a bachelor's degree or higher", "census"),
    ("poverty_rate", "Poverty rate", "census"),
    ("vacancy_rate", "Housing vacancy rate", "census"),
    ("unemployment_rate", "Unemployment rate", "census"),
    ("median_year_built", "Median year housing was built", "census"),
    ("hispanic_share", "Hispanic or Latino share", "race"),
    ("black_share", "Black (non-Hispanic) share", "race"),
    ("white_share", "White (non-Hispanic) share", "race"),
    ("asian_share", "Asian (non-Hispanic) share", "race"),
    ("rent_growth_prior", "Rent growth over the previous period", "trend"),
    ("income_growth_prior", "Income growth over the previous period", "trend"),
    ("pressure_prior", "Rent growth minus income growth, previous period", "trend"),
    ("amenity_density", "Cafes, restaurants, bars and groceries per km² (ZIP)", "business"),
    ("establishment_density", "All business establishments per km² (ZIP)", "business"),
    ("amenity_share", "Amenity share of all establishments (ZIP)", "business"),
    ("amenity_growth", "Two-year growth in amenity businesses (ZIP)", "business"),
    ("establishment_growth", "Two-year growth in all establishments (ZIP)", "business"),
]
FEATURE_KEYS = [key for key, _, _ in FEATURES]
FEATURE_LABELS = {key: label for key, label, _ in FEATURES}
FEATURE_GROUPS = {key: group for key, _, group in FEATURES}


@dataclass(frozen=True)
class Period:
    """One decision point: features observed at `year`, outcome measured at `outcome_year`."""
    name: str
    year: int
    trend_year: int
    zbp_year: int
    zbp_prior_year: int
    outcome_year: int | None


PERIODS = {
    "train": Period("train", 2014, 2010, 2014, 2012, 2019),
    "test": Period("test", 2019, 2015, 2019, 2017, 2024),
    "forecast": Period("forecast", 2024, 2020, 2023, 2021, None),
}


def ratio(numerator: float | None, denominator: float | None) -> float | None:
    return numerator / denominator if numerator is not None and denominator else None


def growth(new: float | None, old: float | None) -> float | None:
    return new / old - 1 if new is not None and old else None


def zip_features(counts: Mapping[str, Mapping[str, int]], prior: Mapping[str, Mapping[str, int]],
                 land_km2: Mapping[str, float]) -> dict[str, dict[str, float]]:
    result = {}
    for zcta, row in counts.items():
        area = land_km2.get(zcta)
        total, amenity = row.get(business.TOTAL, 0), business.amenity_count(row)
        if not area or total <= 0:
            continue
        before = prior.get(zcta, {})
        result[zcta] = {"amenity_density": amenity / area, "establishment_density": total / area,
                        "amenity_share": amenity / total,
                        # log1p keeps tiny ZIPs from producing infinite growth rates.
                        "amenity_growth": math.log1p(amenity) - math.log1p(business.amenity_count(before)),
                        "establishment_growth": math.log1p(total) - math.log1p(before.get(business.TOTAL, 0))}
    return result


def tract_zip_features(weights: Mapping[str, Mapping[str, float]], zips: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float]]:
    """Land-area-weighted average of ZIP features over the ZIPs overlapping each tract."""
    result = {}
    for tract, shares in weights.items():
        usable = {z: w for z, w in shares.items() if z in zips and w > 0}
        total = sum(usable.values())
        if total <= 0:
            continue
        result[tract] = {key: sum(w * zips[z][key] for z, w in usable.items()) / total
                         for key in next(iter(zips.values()))}
    return result


def tract_rows(acs: Mapping[str, Mapping[str, Any]], trend: Mapping[str, Mapping[str, Any]],
               zip_by_tract: Mapping[str, Mapping[str, float]]) -> dict[str, dict[str, float | None]]:
    """Feature values per tract. Missing inputs stay None; models impute explicitly."""
    county = {key: statistics.median(v for v in (number(r, var) for r in acs.values()) if v)
              for key, var in [("income", "B19013_001E"), ("rent", "B25064_001E"), ("home", "B25077_001E")]}
    rows: dict[str, dict[str, float | None]] = {}
    for geoid, row in acs.items():
        population = number(row, "B01003_001E")
        if not population or population < 200:
            continue
        def share(*keys: str, of: str) -> float | None:
            parts = [number(row, k) for k in keys]
            return ratio(sum(p for p in parts if p is not None), number(row, of)) if all(p is not None for p in parts) else None
        income, rent = number(row, "B19013_001E"), number(row, "B25064_001E")
        earlier = trend.get(geoid, {})
        rent_growth = growth(rent, number(earlier, "B25064_001E"))
        income_growth = growth(income, number(earlier, "B19013_001E"))
        year_built = number(row, "B25035_001E")
        features: dict[str, float | None] = {
            "log_population": math.log(population),
            "income_vs_county": ratio(income, county["income"]),
            "rent_vs_county": ratio(rent, county["rent"]),
            "home_value_vs_county": ratio(number(row, "B25077_001E"), county["home"]),
            "rent_income_pct": number(row, "B25071_001E"),
            "rent_burden": rent_burden_share(row),
            "renter_share": renter_share(row),
            "bachelor_share": share("B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E", of="B15003_001E"),
            "poverty_rate": share("B17001_002E", of="B17001_001E"),
            "vacancy_rate": share("B25002_003E", of="B25002_001E"),
            "unemployment_rate": share("B23025_005E", of="B23025_003E"),
            "median_year_built": year_built if year_built and year_built > 1900 else None,
            "hispanic_share": share("B03002_012E", of="B03002_001E"),
            "black_share": share("B03002_004E", of="B03002_001E"),
            "white_share": share("B03002_003E", of="B03002_001E"),
            "asian_share": share("B03002_006E", of="B03002_001E"),
            "rent_growth_prior": rent_growth,
            "income_growth_prior": income_growth,
            "pressure_prior": rent_growth - income_growth if rent_growth is not None and income_growth is not None else None,
        }
        features.update({key: zip_by_tract.get(geoid, {}).get(key) for key, _, group in FEATURES if group == "business"})
        rows[geoid] = features
    return rows


def rent_pressure(before: Mapping[str, Any], after: Mapping[str, Any]) -> float | None:
    """Rent growth minus household-income growth between two ACS periods."""
    rent = growth(number(after, "B25064_001E"), number(before, "B25064_001E"))
    income = growth(number(after, "B19013_001E"), number(before, "B19013_001E"))
    return rent - income if rent is not None and income is not None else None


def top_quartile_labels(pressures: Mapping[str, float]) -> tuple[dict[str, int], float]:
    """1 when a tract's pressure is in the top quarter of all tracts with a value."""
    values = sorted(pressures.values())
    cutoff = values[int(.75 * len(values))]
    return {g: int(v >= cutoff) for g, v in pressures.items()}, cutoff


def majority_group(row: Mapping[str, float | None]) -> str:
    shares = {"Hispanic or Latino": row.get("hispanic_share"), "Black": row.get("black_share"),
              "White": row.get("white_share"), "Asian": row.get("asian_share")}
    known = {k: v for k, v in shares.items() if v is not None}
    return max(known, key=lambda k: known[k]) if known else "Unknown"
