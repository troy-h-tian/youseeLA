"""Derive ratios from counts and preserve uncertainty instead of filling zeros."""

import math
from dataclasses import dataclass
from typing import Mapping


def number(row: Mapping[str, object], key: str) -> float | None:
    try:
        value = float(str(row.get(key)))
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def rent_burden_share(row: Mapping[str, object]) -> float | None:
    total, excluded = number(row, "B25070_001E"), number(row, "B25070_011E")
    counts = [number(row, f"B25070_{i:03d}E") for i in range(7, 11)]
    if total is None or excluded is None or any(v is None for v in counts):
        return None
    denominator = total - excluded
    numerator = sum(v for v in counts if v is not None)
    return numerator / denominator if denominator > 0 and numerator <= denominator else None


def renter_share(row: Mapping[str, object]) -> float | None:
    total, renters = number(row, "B25003_001E"), number(row, "B25003_003E")
    if total is None or renters is None or total <= 0 or renters > total:
        return None
    return renters / total


@dataclass(frozen=True)
class Pressure:
    value: float | None
    gap: float | None
    lower_bound: float | None
    upper_bound: float | None
    reason: str


def affordability_pressure(old: Mapping[str, object], new: Mapping[str, object], cap: float = 0.20,
                           allow_uncertain: bool = False) -> Pressure:
    if not math.isfinite(cap) or cap <= 0:
        raise ValueError("Scaling cap must be positive")
    keys = ["B25064_001E", "B25064_001M", "B19013_001E", "B19013_001M"]
    values = [number(row, key) for row in [old, new] for key in keys]
    if any(v is None for v in values):
        return Pressure(None, None, None, None, "Missing rent/income estimates or margins of error")
    ro, rom, io, iom, rn, rnm, inn, inm = (float(v) for v in values if v is not None)
    if min(ro-rom, io-iom, rn-rnm, inn-inm) <= 0:
        return Pressure(None, None, None, None, "Unusable estimate uncertainty interval")
    gap = rn / ro - inn / io
    lower = (rn-rnm)/(ro+rom) - (inn+inm)/(io-iom)
    upper = (rn+rnm)/(ro-rom) - (inn-inm)/(io+iom)
    if lower <= 0 < upper:
        return Pressure(min(1.0, max(0.0, gap) / cap) if allow_uncertain else None, gap, lower, upper,
                        "Affordability-change direction is uncertain; use the sensitivity range, not the point estimate alone")
    return Pressure(min(1.0, max(0.0, gap) / cap), gap, lower, upper,
                    "Descriptive overlapping-window proxy; bounds are sensitivity bounds, not a joint confidence interval")
