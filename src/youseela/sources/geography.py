"""Use official full tract boundaries; never guess tracts from place names."""

from typing import Any

import httpx
from shapely.geometry import shape

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
