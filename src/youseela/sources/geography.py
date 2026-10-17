"""Use official full tract boundaries; never guess tracts from place names."""

import math
from typing import Any

import httpx
import shapely
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"


def intersecting_tracts(city: dict[str, Any], features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    city_shape = shape(city)
    return [feature for feature in features if shape(feature["geometry"]).intersection(city_shape).area > 1e-10]


def query_layer(service: str, layer: int, where: str, client: httpx.Client,
                geometry: str | None = None) -> dict[str, Any]:
    params: dict[str, str] = {"where":where,"outFields":"*","returnGeometry":"true","outSR":"4326","f":"geojson"}
    if geometry:
        params.update(geometry=geometry, geometryType="esriGeometryEnvelope", inSR="4326", spatialRel="esriSpatialRelIntersects")
    response = client.get(f"{BASE}/{service}/MapServer/{layer}/query", params=params)
    response.raise_for_status()
    data = response.json()
    if "error" in data or "features" not in data or data.get("exceededTransferLimit"):
        raise ValueError("Geography query failed or was truncated; narrow the requested area")
    return data


def local_metres(geometry: BaseGeometry, latitude: float) -> BaseGeometry:
    """Equirectangular projection around one latitude; accurate to well under 1% across a tract."""
    scale_x = 111_320 * math.cos(math.radians(latitude))
    return shapely.transform(geometry, lambda coords: coords * [scale_x, 110_540])


def boundary_shift(earlier: dict[str, Any], later: dict[str, Any]) -> dict[str, Any]:
    """Measure how far two vintages of one tract boundary differ, instead of requiring exact equality."""
    a, b = shape(earlier), shape(later)
    latitude = a.centroid.y
    a_m, b_m = local_metres(a, latitude), local_metres(b, latitude)
    return {"exact_equal": a.equals(b),
            "area_difference_share": a_m.symmetric_difference(b_m).area / a_m.area,
            "max_shift_m": a_m.hausdorff_distance(b_m)}


def comparable_boundaries(shift: dict[str, Any], max_shift_m: float = 5, max_area_share: float = .001) -> bool:
    """Digitizing updates move vertices by centimetres; a real boundary change moves whole blocks."""
    return shift["max_shift_m"] <= max_shift_m and shift["area_difference_share"] <= max_area_share


def tract_layer(year: int, client: httpx.Client) -> int:
    """The tract layer's number differs between ACS vintages of TIGERweb, so look it up by name."""
    response = client.get(f"{BASE}/tigerWMS_ACS{year}/MapServer", params={"f": "json"})
    response.raise_for_status()
    layers = [layer["id"] for layer in response.json().get("layers", []) if layer["name"] == "Census Tracts"]
    if not layers:
        raise ValueError(f"No Census Tracts layer in the ACS {year} TIGERweb service")
    return layers[0]


def compare_vintages(geoids: list[str], earlier_year: int, later_year: int,
                     client: httpx.Client | None = None) -> dict[str, Any]:
    owned = client is None
    client = client or httpx.Client(timeout=60)
    try:
        where = "GEOID IN (" + ",".join(f"'{g}'" for g in geoids) + ")"
        layers = {year: tract_layer(year, client) for year in (earlier_year, later_year)}
        shapes = {year: {str(f["properties"]["GEOID"]): f["geometry"]
                         for f in query_layer(f"tigerWMS_ACS{year}", layers[year], where, client)["features"]}
                  for year in (earlier_year, later_year)}
    finally:
        if owned:
            client.close()
    tracts = {}
    for geoid in geoids:
        if geoid not in shapes[earlier_year] or geoid not in shapes[later_year]:
            tracts[geoid] = {"comparable": False, "reason": "Tract missing from one vintage"}
            continue
        shift = boundary_shift(shapes[earlier_year][geoid], shapes[later_year][geoid])
        tracts[geoid] = {**{k: round(v, 6) if isinstance(v, float) else v for k, v in shift.items()},
                         "comparable": comparable_boundaries(shift)}
    return {"sources": [f"{BASE}/tigerWMS_ACS{year}/MapServer/{layers[year]}" for year in (earlier_year, later_year)],
            "rule": "Comparable when the maximum boundary shift is at most 5 m and the area difference is at most 0.1%.",
            "tracts": tracts}


def discover_inglewood(client: httpx.Client | None = None) -> dict[str, Any]:
    owned = client is None
    client = client or httpx.Client(timeout=60)
    try:
        # Census 2020 layers are explicit, unlike the changing current-year layers.
        city = query_layer("Places_CouSub_ConCity_SubMCD", 25, "STATE='06' AND BASENAME='Inglewood'", client)
        if len(city["features"]) != 1:
            raise ValueError("Could not uniquely identify Inglewood city")
        polygon = city["features"][0]["geometry"]
        bounds = ",".join(str(v) for v in shape(polygon).bounds)
        tracts = query_layer("Tracts_Blocks", 10, "STATE='06' AND COUNTY='037'", client, bounds)
        features = intersecting_tracts(polygon, tracts["features"])
        return {"type":"FeatureCollection", "features":features,
                "source":f"{BASE}/Tracts_Blocks/MapServer/10", "boundary_vintage":"Census 2020",
                "scope":"Full tracts intersecting Inglewood, not clipped to city boundaries",
                "city_geometry":polygon}
    finally:
        if owned:
            client.close()
