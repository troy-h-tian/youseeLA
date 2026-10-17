"""Census ZIP Business Patterns amenity counts, after Glaeser, Kim & Luca's Yelp categories."""

import csv
import io
import zipfile
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import shape

from youseela.sources.geography import query_layer

# Cafes, full-service restaurants, bars and groceries grow in gentrifying areas (Glaeser, Kim & Luca 2018).
AMENITY_NAICS = {"722515": "Snack and nonalcoholic beverage bars (cafes)", "722511": "Full-service restaurants",
                 "722410": "Drinking places", "445110": "Supermarkets and grocery stores"}
TOTAL = "------"


def zbp_url(year: int) -> str:
    # The four amenity codes are unchanged across the NAICS 2012 and 2017 editions, and the
    # zip/naics/est columns are the same in every detail file since 2012.
    if not 2012 <= year <= 2100:
        raise ValueError("ZIP Business Patterns detail files from 2012 onward are supported")
    return f"https://www2.census.gov/programs-surveys/cbp/datasets/{year}/zbp{year % 100:02d}detail.zip"


def download_zbp(year: int, destination: Path, client: httpx.Client | None = None) -> Path:
    """Cache the national detail file; it is large, so stream it to disk once."""
    if destination.exists():
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    owned = client is None
    client = client or httpx.Client(timeout=300, follow_redirects=True)
    temporary = destination.with_suffix(".part")
    try:
        with client.stream("GET", zbp_url(year)) as response:
            if response.status_code != 200:
                raise ValueError(f"ZIP Business Patterns {year} returned HTTP {response.status_code}")
            with temporary.open("wb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
        temporary.replace(destination)
        return destination
    finally:
        if owned:
            client.close()


def read_zbp(path: Path, zips: set[str]) -> dict[str, dict[str, int]]:
    """Establishment counts by ZIP and NAICS. ZBP omits zero rows, so absent codes are counted as zero."""
    with zipfile.ZipFile(path) as archive:
        members = [name for name in archive.namelist() if name.endswith(".txt")]
        if len(members) != 1:
            raise ValueError("Expected one ZBP detail text file in the archive")
        with archive.open(members[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="latin-1"))
            result: dict[str, dict[str, int]] = {}
            for row in reader:
                if row["zip"] in zips and row["naics"] in {TOTAL, *AMENITY_NAICS}:
                    result.setdefault(row["zip"], {})[row["naics"]] = int(row["est"])
    return result


def amenity_count(counts: dict[str, int]) -> int:
    return sum(counts.get(code, 0) for code in AMENITY_NAICS)


def dominant_zctas(areas: dict[str, dict[str, Any]], zctas: list[dict[str, Any]]) -> dict[str, tuple[str, float]]:
    """Map each tract to the ZCTA covering most of its area, with that coverage fraction."""
    shapes = [(str(f["properties"]["ZCTA5"]), shape(f["geometry"])) for f in zctas]
    result: dict[str, tuple[str, float]] = {}
    for area_id, geometry in areas.items():
        tract = shape(geometry)
        if tract.area <= 0:
            continue
        overlaps = [(zcta, tract.intersection(polygon).area / tract.area) for zcta, polygon in shapes]
        best = max(overlaps, key=lambda item: item[1], default=None)
        if best and best[1] > 0:
            result[area_id] = best
    return result


def fetch_zctas(bbox: tuple[float, float, float, float], client: httpx.Client | None = None) -> list[dict[str, Any]]:
    owned = client is None
    client = client or httpx.Client(timeout=60)
    try:
        # Layer 1 is the explicit 2020 Census ZCTA vintage, matching the 2020 tract boundaries.
        return query_layer("PUMA_TAD_TAZ_UGA_ZCTA", 1, "1=1", client, ",".join(map(str, bbox)))["features"]
    finally:
        if owned:
            client.close()
