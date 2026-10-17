"""Download and cache every raw input for the predictive models. Re-runs reuse cached files."""

import csv
import io
import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

from youseela.sources import business
from youseela.sources.census import fetch_county

RAW = Path("data/raw/prediction")

# Rent and income only for the "previous trend" years; full features for the decision years.
TREND_VARIABLES = ["B25064_001E", "B19013_001E"]
FEATURE_VARIABLES = [
    "NAME", "B01003_001E", "B19013_001E", "B19013_001M", "B25064_001E", "B25064_001M", "B25071_001E",
    "B25070_001E", "B25070_007E", "B25070_008E", "B25070_009E", "B25070_010E", "B25070_011E",
    "B25003_001E", "B25003_003E", "B15003_001E", "B15003_022E", "B15003_023E", "B15003_024E", "B15003_025E",
    "B03002_001E", "B03002_003E", "B03002_004E", "B03002_006E", "B03002_012E",
    "B25077_001E", "B17001_001E", "B17001_002E", "B25002_001E", "B25002_003E", "B25035_001E",
    "B23025_003E", "B23025_005E"]
FEATURE_YEARS = (2014, 2019, 2024)
TREND_YEARS = (2010, 2015, 2020)
ZBP_YEARS = (2012, 2014, 2017, 2019, 2021, 2023)
ZCTA_FEATURE_YEARS = (2014, 2019, 2024)
ZCTA_TREND_YEARS = (2011, 2015, 2020)  # ZCTA-level ACS starts in 2011

ZCTA_TRACT_2010 = "https://www2.census.gov/geo/docs/maps-data/data/rel/zcta_tract_rel_10.txt"
ZCTA_TRACT_2020 = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_tract20_natl.txt"
TRACT_RELATIONSHIP = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/tract/tab20_tract20_tract10_st06.txt"
LA_BUSINESSES = "https://data.lacity.org/resource/r4uk-afju.json"
LA_BUSINESS_PAGE = "https://data.lacity.org/Administration-Finance/Listing-of-All-Businesses/r4uk-afju"


def cached(path: Path, fetch: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text())
    value = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)
    return value


def download_text(url: str, path: Path) -> str:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=300, follow_redirects=True) as client:
            response = client.get(url)
            if response.status_code != 200:
                raise ValueError(f"{url} returned HTTP {response.status_code}")
            path.write_bytes(response.content)
    return path.read_text(encoding="utf-8-sig", errors="replace")


def acs(year: int, variables: list[str], key: str) -> dict[str, dict[str, Any]]:
    name = "features" if variables is FEATURE_VARIABLES else "trend"
    return cached(RAW / f"acs-{name}-{year}.json", lambda: fetch_county(year, key, variables=variables))


def zcta_weights_2010() -> dict[str, dict[str, float]]:
    """2010 tract -> {ZCTA: share of the tract's land in that ZCTA}, LA County only."""
    text = download_text(ZCTA_TRACT_2010, RAW / "zcta-tract-2010.txt")
    weights: dict[str, dict[str, float]] = {}
    for raw in csv.DictReader(io.StringIO(text)):
        row = {k.strip(): v for k, v in raw.items()}  # the published header has stray spaces
        if row["STATE"] == "06" and row["COUNTY"] == "037" and float(row["TRAREALAND"] or 0) > 0:
            weights.setdefault(row["GEOID"], {})[row["ZCTA5"]] = float(row["AREALANDPT"]) / float(row["TRAREALAND"])
    return weights


def zcta_weights_2020() -> dict[str, dict[str, float]]:
    text = download_text(ZCTA_TRACT_2020, RAW / "zcta-tract-2020.txt")
    land: dict[str, float] = {}
    parts: dict[str, dict[str, float]] = {}
    for row in csv.DictReader(io.StringIO(text), delimiter="|"):
        tract, zcta = row["GEOID_TRACT_20"], row["GEOID_ZCTA5_20"]
        if not tract.startswith("06037") or not zcta:
            continue
        land[tract] = float(row["AREALAND_TRACT_20"] or 0)
        parts.setdefault(tract, {})[zcta] = float(row["AREALAND_PART"] or 0)
    return {t: {z: a / land[t] for z, a in zs.items()} for t, zs in parts.items() if land.get(t)}


def zcta_land_km2() -> dict[str, float]:
    """ZCTA land area, for converting establishment counts to densities."""
    text = download_text(ZCTA_TRACT_2020, RAW / "zcta-tract-2020.txt")
    return {row["GEOID_ZCTA5_20"]: float(row["AREALAND_ZCTA5_20"]) / 1e6
            for row in csv.DictReader(io.StringIO(text), delimiter="|") if row["GEOID_ZCTA5_20"]}


def zbp_counts(year: int, zips: set[str]) -> dict[str, dict[str, int]]:
    def load() -> dict[str, dict[str, int]]:
        archive = business.download_zbp(year, RAW / f"zbp{year}.zip")
        return business.read_zbp(archive, zips)
    return cached(RAW / f"zbp-counts-{year}.json", load)


def acs_zcta(year: int, variables: list[str], key: str, zips: set[str]) -> dict[str, dict[str, Any]]:
    """ACS for ZIP code tabulation areas. Before 2020 the API nests ZCTAs in states; from 2020 it does not."""
    name = "features" if variables is FEATURE_VARIABLES else "trend"
    def load() -> dict[str, dict[str, Any]]:
        params = {"get": ",".join(variables), "for": "zip code tabulation area:*", "key": key}
        if year < 2020:
            params["in"] = "state:06"
        with httpx.Client(timeout=300) as client:
            response = client.get(f"https://api.census.gov/data/{year}/acs/acs5", params=params)
        if response.status_code != 200 or not response.text.startswith("["):
            raise ValueError(f"ACS {year} ZCTA request failed with HTTP {response.status_code}")
        header, *table = response.json()
        column = header.index("zip code tabulation area")
        return {row[column]: dict(zip(header, row)) for row in table if row[column] in zips}
    return cached(RAW / f"acs-zcta-{name}-{year}.json", load)


def la_city_businesses() -> list[dict[str, Any]]:
    """City of LA business locations open at any point from 2015 through 2019.

    Closed accounts lose their coordinates and NAICS codes in this dataset, so location is the ZIP code and
    business type comes from the name, both of which every record keeps.
    """
    def load() -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        where = ("location_start_date <= '2019-12-31T00:00:00' AND (location_end_date IS NULL OR "
                 "location_end_date > '2014-12-31T00:00:00') AND council_district != 0")
        select = "location_account,business_name,dba_name,location_start_date,location_end_date,zip_code"
        with httpx.Client(timeout=300) as client:
            for offset in range(0, 5_000_000, 50_000):
                response = client.get(LA_BUSINESSES, params={"$select": select, "$where": where, "$order": "location_account",
                                                             "$limit": "50000", "$offset": str(offset)})
                response.raise_for_status()
                page = response.json()
                # NAICS is deliberately not kept: the City removes it from closed accounts, so it would leak the outcome.
                rows.extend({"id": item["location_account"], "name": item.get("dba_name") or item.get("business_name") or "",
                             "start": (item.get("location_start_date") or "")[:10], "end": (item.get("location_end_date") or "")[:10] or None,
                             "zip": (item.get("zip_code") or "")[:5]} for item in page)
                print(f"LA City businesses: {len(rows)} rows after offset {offset}", flush=True)
                if len(page) < 50_000:
                    break
        return rows
    return cached(RAW / "la-city-businesses-zip.json", load)


def fetch_all() -> None:
    key = dotenv_values(".env").get("CENSUS_API_KEY") or os.environ.get("CENSUS_API_KEY", "")
    for year in FEATURE_YEARS:
        print(f"ACS {year}: {len(acs(year, FEATURE_VARIABLES, key))} tracts", flush=True)
    for year in TREND_YEARS:
        print(f"ACS trend {year}: {len(acs(year, TREND_VARIABLES, key))} tracts", flush=True)
    download_text(TRACT_RELATIONSHIP, RAW / "tract20-tract10-ca.txt")
    zips = {z for weights in (zcta_weights_2010(), zcta_weights_2020()) for zs in weights.values() for z in zs}
    for year in ZBP_YEARS:
        print(f"ZBP {year}: {len(zbp_counts(year, zips))} ZIPs", flush=True)
    for year in ZCTA_FEATURE_YEARS:
        print(f"ACS ZCTA {year}: {len(acs_zcta(year, FEATURE_VARIABLES, key, zips))} ZIPs", flush=True)
    for year in ZCTA_TREND_YEARS:
        print(f"ACS ZCTA trend {year}: {len(acs_zcta(year, TREND_VARIABLES, key, zips))} ZIPs", flush=True)
    print(f"LA City businesses: {len(la_city_businesses())} rows", flush=True)


if __name__ == "__main__":
    fetch_all()
