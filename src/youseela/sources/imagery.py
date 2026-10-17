"""Bounded Mapillary discovery. Returned thumbnails stay in ignored raw data."""

import math
from typing import Any

import httpx


def discover_images(bbox: tuple[float, float, float, float], token: str, limit: int = 50,
                    client: httpx.Client | None = None) -> dict[str, Any]:
    if not token:
        raise ValueError("Set MAPILLARY_ACCESS_TOKEN in .env before image discovery")
    west, south, east, north = bbox
    if not all(math.isfinite(v) for v in bbox) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Bounding box must be west,south,east,north")
    if east-west > .011 or north-south > .011:
        raise ValueError("Use a small bounding box (at most .01 degrees per side) and inspect coverage before expanding")
    if not 1 <= limit <= 100:
        raise ValueError("Image query limit must be between 1 and 100")
    owned = client is None
    client = client or httpx.Client(timeout=30)
    try:
        response = client.get("https://graph.mapillary.com/images",
                              headers={"Authorization":f"OAuth {token}"},
                              params={"bbox":",".join(map(str,bbox)),"limit":limit,
                                      "fields":"id,captured_at,geometry,creator,thumb_1024_url"})
        if response.status_code != 200:
            raise ValueError(f"Mapillary returned HTTP {response.status_code}; check token, scope and query bounds")
        payload = response.json()
        if "data" not in payload or not isinstance(payload["data"],list):
            raise ValueError("Mapillary returned unexpected image metadata")
        # Pagination links can contain tokens. Do not save or echo them.
        return {"source":"Mapillary","bbox":list(bbox),"images":payload["data"],
                "has_more":bool(payload.get("paging",{}).get("next")),
                "note":"Discovery only; inspect dates, license, locations and both residential/commercial coverage before use."}
    except httpx.HTTPError:
        raise ValueError("Mapillary request failed; check connectivity and token") from None
    finally:
        if owned:
            client.close()
