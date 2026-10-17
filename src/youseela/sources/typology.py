"""Urban Displacement Project typologies as an external benchmark, never a score input."""

import csv
import io
from collections import defaultdict
from typing import Any

import httpx

# Pin the commit so a later upstream revision cannot silently change the benchmark.
UDP_COMMIT = "a2479c79e630cdaed9add49bb3c05db8a5e59d18"
UDP_URL = ("https://raw.githubusercontent.com/urban-displacement/displacement-typologies/"
           f"{UDP_COMMIT}/data/outputs/typologies/LosAngeles_typology_output.csv")
UDP_PAGE = "https://github.com/urban-displacement/displacement-typologies"
RELATIONSHIP_URL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_st06.txt"

LABELS = {"LISD": "Low-income / susceptible to displacement", "OD": "Ongoing displacement",
          "ARG": "At risk of gentrification", "EOG": "Early/ongoing gentrification",
          "AdvG": "Advanced gentrification", "SMMI": "Stable moderate/mixed income",
          "ARE": "At risk of becoming exclusive", "BE": "Becoming exclusive",
          "SAE": "Stable/advanced exclusive"}


def parse_udp(text: str) -> dict[str, str]:
    """Return 2010 tract GEOID -> typology code. Ambiguous or empty categories are omitted."""
    result: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(text)):
        geoid = str(row.get("GEOID", "")).split(".")[0].zfill(11)
        # typ_cat looks like "['OD']"; combined categories such as "['AdvG', 'BE']" are not a single benchmark label.
        codes = [c.strip(" '\"") for c in str(row.get("typ_cat", "")).strip("[]").split(",") if c.strip(" '\"")]
        if len(geoid) == 11 and geoid.isdigit() and len(codes) == 1 and codes[0] in LABELS:
            result[geoid] = codes[0]
    if not result:
        raise ValueError("UDP typology file had no usable tract categories")
    return result


def parse_relationship(text: str) -> dict[str, list[dict[str, Any]]]:
    """Census 2020-to-2010 tract relationship rows grouped by 2020 GEOID."""
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in csv.DictReader(io.StringIO(text.lstrip("﻿")), delimiter="|"):
        rows[row["GEOID_TRACT_20"]].append({"tract10": row["GEOID_TRACT_10"], "part": int(row["AREALAND_PART"]),
                                            "land20": int(row["AREALAND_TRACT_20"]), "land10": int(row["AREALAND_TRACT_10"])})
    return rows


def equivalent_2010_tract(geoid20: str, relationship: dict[str, list[dict[str, Any]]],
                          threshold: float = .95) -> str | None:
    """A 2010 tract counts as equivalent only when each covers at least `threshold` of the other's land."""
    parts = relationship.get(geoid20, [])
    if not parts:
        return None
    best = max(parts, key=lambda p: p["part"])
    if best["land20"] <= 0 or best["land10"] <= 0:
        return None
    if best["part"]/best["land20"] >= threshold and best["part"]/best["land10"] >= threshold:
        return best["tract10"]
    return None


def fetch_text(url: str, client: httpx.Client | None = None) -> str:
    owned = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True)
    try:
        response = client.get(url)
        if response.status_code != 200:
            raise ValueError(f"Source returned HTTP {response.status_code}: {url}")
        return response.text
    finally:
        if owned:
            client.close()
