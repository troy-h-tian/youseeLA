"""Fetch ACS tables with explicit errors for missing keys and malformed data."""

import csv
import json
from pathlib import Path
from typing import Any

import httpx

VARIABLES = ["NAME", "B25070_001E", "B25070_011E", "B25070_007E", "B25070_008E",
             "B25070_009E", "B25070_010E", "B25003_001E", "B25003_003E",
             "B25064_001E", "B25064_001M", "B19013_001E", "B19013_001M"]


class CensusAccessError(ValueError):
    """A safe-to-display source error, without request URLs containing keys."""


def parse_table(table: list[list[Any]]) -> dict[str, dict[str, Any]]:
    if not table or not isinstance(table[0], list):
        raise CensusAccessError("Expected the Census API header-and-rows JSON format")
    headers = table[0]
    if not all(name in headers for name in ["state", "county", "tract"]):
        raise CensusAccessError("Census data must include state, county and tract identifiers")
    result: dict[str, dict[str, Any]] = {}
    for values in table[1:]:
        if len(values) != len(headers):
            raise CensusAccessError("Census row length does not match the header")
        row = dict(zip(headers, values))
        geoid = str(row["state"]).zfill(2)+str(row["county"]).zfill(3)+str(row["tract"]).zfill(6)
        if len(geoid) != 11 or not geoid.isdigit() or geoid in result:
            raise CensusAccessError("Invalid or duplicate Census tract GEOID")
        result[geoid] = row
    return result


def fetch_county(year: int, api_key: str, *, state: str = "06", county: str = "037",
                 client: httpx.Client | None = None) -> dict[str, dict[str, Any]]:
    if not api_key:
        raise CensusAccessError("Set CENSUS_API_KEY in .env or import an official CSV")
    if year < 2009 or year > 2100 or not state.isdigit() or not county.isdigit():
        raise CensusAccessError("Invalid Census year/state/county")
    owned = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=True)
    try:
        response = client.get(f"https://api.census.gov/data/{year}/acs/acs5",
                              params={"get": ",".join(VARIABLES), "for": "tract:*", "in": f"state:{state} county:{county}", "key": api_key})
        if response.status_code != 200:
            raise CensusAccessError(f"Census returned HTTP {response.status_code}; check key and dataset availability")
        try:
            table = response.json()
        except ValueError:
            raise CensusAccessError("Census returned HTML instead of data; verify CENSUS_API_KEY") from None
        if not isinstance(table, list):
            raise CensusAccessError("Unexpected Census response; verify dataset and key")
        return parse_table(table)
    except httpx.HTTPError:
        raise CensusAccessError("Census network request failed; check connectivity and retry") from None
    finally:
        if owned:
            client.close()


def read_rows(path: Path) -> dict[str, dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open(newline="") as stream:
            reader = csv.reader(stream)
            return parse_table(list(reader))
    data = json.loads(path.read_text())
    return parse_table(data) if isinstance(data, list) else data
