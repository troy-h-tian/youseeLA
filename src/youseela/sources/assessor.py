"""LA County Assessor roll aggregates. Prop 13 base years reset on sale or new construction."""

import math
import time
from typing import Any

import httpx
from shapely import STRtree
from shapely.geometry import Point, shape

BASE = "https://services.arcgis.com/RmCCgQtiZLDCtblq/arcgis/rest/services"
SERVICES = {range(2006, 2011): "Parcel_Data_2006_2010_Table", range(2011, 2016): "Parcel_Data_2011_2015_Table",
            range(2016, 2021): "Parcel_Data_2016_2020_Table", range(2021, 2026): "Parcel_Data_2021_Table"}
FIELDS = ["AIN", "RollYear", "isTaxableParcel", "Roll_LandBaseYear", "EffectiveYearBuilt", "CENTER_LAT", "CENTER_LON"]
PAGE = 2000
WINDOW_YEARS = 5


def service_url(roll_year: int) -> str:
    for years, name in SERVICES.items():
        if roll_year in years:
            return f"{BASE}/{name}/FeatureServer/0/query"
    raise ValueError("Assessor roll years 2006 through 2025 are supported")


def query_page(client: httpx.Client, url: str, params: dict[str, str], retries: int) -> dict[str, Any]:
    """The county service intermittently times out on large tables; free public reads are safe to retry."""
    problem = "no attempt made"
    for attempt in range(retries + 1):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            response = client.get(url, params=params)
        except httpx.TimeoutException:
            problem = "request timed out"
            continue
        if response.status_code != 200:
            problem = f"HTTP {response.status_code}"
            continue
        data = response.json()
        if "features" in data and "error" not in data:
            return data
        problem = f"service error {data.get('error', {}).get('code', 'unknown')}"
    raise ValueError(f"Assessor service failed after {retries + 1} attempts ({problem}); check roll year and query bounds")


def fetch_parcels(roll_year: int, bbox: tuple[float, float, float, float],
                  client: httpx.Client | None = None, max_pages: int = 100, retries: int = 3,
                  fields: list[str] = FIELDS) -> list[dict[str, Any]]:
    west, south, east, north = bbox
    if not all(math.isfinite(v) for v in bbox) or not (west < east and south < north):
        raise ValueError("Bounding box must be west,south,east,north")
    url = service_url(roll_year)
    where = (f"RollYear='{roll_year}' AND CENTER_LAT BETWEEN {south} AND {north} "
             f"AND CENTER_LON BETWEEN {west} AND {east}")
    owned = client is None
    client = client or httpx.Client(timeout=120)
    parcels: list[dict[str, Any]] = []
    try:
        for page in range(max_pages):
            params = {"where": where, "outFields": ",".join(fields), "returnGeometry": "false",
                      "orderByFields": "OBJECTID", "resultOffset": str(page*PAGE),
                      "resultRecordCount": str(PAGE), "f": "json"}
            data = query_page(client, url, params, retries)
            parcels.extend(item["attributes"] for item in data["features"])
            if not data.get("exceededTransferLimit") and len(data["features"]) < PAGE:
                return parcels
        raise ValueError("Assessor query exceeded the page limit; narrow the bounding box")
    finally:
        if owned:
            client.close()


def year(value: Any) -> int | None:
    try:
        result = int(str(value))
    except (TypeError, ValueError):
        return None
    return result if 1800 <= result <= 2100 else None


def tract_activity(parcels: list[dict[str, Any]], areas: dict[str, dict[str, Any]],
                   roll_year: int) -> dict[str, dict[str, int]]:
    """Count taxable parcels per tract, and those reassessed or built/renovated in the roll's five-year window."""
    ids = list(areas)
    shapes = [shape(areas[i]) for i in ids]
    tree = STRtree(shapes)
    first = roll_year - WINDOW_YEARS + 1
    counts = {i: {"taxable": 0, "reassessed": 0, "built_or_renovated": 0} for i in ids}
    seen: set[str] = set()
    for parcel in parcels:
        ain = str(parcel.get("AIN", ""))
        lat, lon = parcel.get("CENTER_LAT"), parcel.get("CENTER_LON")
        # Public and exempt parcels never reassess on sale, so they would dilute the turnover share.
        if (str(parcel.get("RollYear")) != str(roll_year) or parcel.get("isTaxableParcel") != "Y" or not ain or ain in seen
                or not isinstance(lat, (int, float)) or not isinstance(lon, (int, float))):
            continue
        seen.add(ain)
        point = Point(lon, lat)
        match = next((ids[i] for i in tree.query(point) if shapes[i].covers(point)), None)
        if match is None:
            continue
        tally = counts[match]
        tally["taxable"] += 1
        base = year(parcel.get("Roll_LandBaseYear"))
        built = year(parcel.get("EffectiveYearBuilt"))
        tally["reassessed"] += base is not None and first <= base <= roll_year
        tally["built_or_renovated"] += built is not None and first <= built <= roll_year
    return counts
