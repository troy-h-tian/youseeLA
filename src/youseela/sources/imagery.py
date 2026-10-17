"""Bounded Mapillary discovery. Returned thumbnails stay in ignored raw data."""

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

FIELDS = ("id,captured_at,geometry,computed_geometry,compass_angle,computed_compass_angle,"
          "is_pano,creator,thumb_1024_url")


def milliseconds(day: date) -> float:
    return datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).timestamp()*1000


def location(item: dict[str, Any]) -> tuple[float, float] | None:
    """Prefer Mapillary's structure-from-motion position over the raw GPS fix."""
    for key in ("computed_geometry", "geometry"):
        coordinates = (item.get(key) or {}).get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) == 2 and all(isinstance(v, (int, float)) for v in coordinates):
            return float(coordinates[0]), float(coordinates[1])
    return None


def bearing_and_distance(origin: tuple[float, float], target: tuple[float, float]) -> tuple[float, float]:
    """Initial compass bearing (degrees) and haversine distance (metres), both points as (lon, lat)."""
    lon1, lat1, lon2, lat2 = map(math.radians, (*origin, *target))
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1)*math.sin(lat2) - math.sin(lat1)*math.cos(lat2)*math.cos(dlon)
    bearing = (math.degrees(math.atan2(y, x)) + 360) % 360
    a = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return bearing, 6371000 * 2 * math.asin(min(1, math.sqrt(a)))


def facing_target(item: dict[str, Any], target: tuple[float, float], max_offset: float) -> dict[str, Any] | None:
    """Annotate an image with its geometry relative to the target; None if the camera does not face it."""
    position = location(item)
    heading = item.get("computed_compass_angle", item.get("compass_angle"))
    if position is None or not isinstance(heading, (int, float)):
        return None
    bearing, distance = bearing_and_distance(position, target)
    offset = abs((heading - bearing + 180) % 360 - 180)
    if offset > max_offset:
        return None
    return {**item, "target_distance_m": round(distance, 1), "target_bearing": round(bearing, 1),
            "heading_offset": round(offset, 1)}


def discover_images(bbox: tuple[float, float, float, float], token: str, limit: int = 50,
                    client: httpx.Client | None = None, captured_after: date | None = None,
                    captured_before: date | None = None, include_panoramas: bool = False, max_pages: int = 1,
                    target: tuple[float, float] | None = None, max_heading_offset: float = 45) -> dict[str, Any]:
    """`target` is (lon, lat): keep only images whose camera points within `max_heading_offset` degrees of it."""
    if not token:
        raise ValueError("Set MAPILLARY_ACCESS_TOKEN in .env before image discovery")
    west, south, east, north = bbox
    if not all(math.isfinite(v) for v in bbox) or not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("Bounding box must be west,south,east,north")
    if east-west > .011 or north-south > .011:
        raise ValueError("Use a small bounding box (at most .01 degrees per side) and inspect coverage before expanding")
    if not 1 <= limit <= 100:
        raise ValueError("Image query limit must be between 1 and 100")
    if not 1 <= max_pages <= 20:
        raise ValueError("Follow between 1 and 20 result pages")
    if captured_after and captured_before and captured_after >= captured_before:
        raise ValueError("captured_after must precede captured_before")
    if not 0 < max_heading_offset <= 180:
        raise ValueError("Heading offset must be between 0 and 180 degrees")
    owned = client is None
    client = client or httpx.Client(timeout=30)
    try:
        params: dict[str, str] | None = {"bbox":",".join(map(str,bbox)), "limit":str(limit), "fields":FIELDS}
        if captured_after:
            params["start_captured_at"] = captured_after.isoformat()+"T00:00:00Z"
        if captured_before:
            params["end_captured_at"] = captured_before.isoformat()+"T00:00:00Z"
        url = "https://graph.mapillary.com/images"
        returned: list[dict[str, Any]] = []
        next_url = None
        for _ in range(max_pages):
            response = client.get(url, headers={"Authorization":f"OAuth {token}"}, params=params)
            if response.status_code != 200:
                raise ValueError(f"Mapillary returned HTTP {response.status_code}; check token, scope and query bounds")
            payload = response.json()
            if "data" not in payload or not isinstance(payload["data"],list):
                raise ValueError("Mapillary returned unexpected image metadata")
            returned.extend(payload["data"])
            # Pagination links can contain tokens. Follow them, but never save or echo them.
            next_url = payload.get("paging",{}).get("next")
            if not next_url or len(payload["data"]) < limit:
                break
            url, params = next_url, None
        images = returned
        if captured_after:
            images = [item for item in images if isinstance(item.get("captured_at"), (int, float))
                      and item["captured_at"] >= milliseconds(captured_after)]
        if captured_before:
            images = [item for item in images if isinstance(item.get("captured_at"), (int, float))
                      and item["captured_at"] < milliseconds(captured_before)]
        panoramas = sum(1 for item in images if item.get("is_pano") is True)
        if not include_panoramas:
            # 360-degree panoramas reach the vision model as distorted equirectangular thumbnails.
            images = [item for item in images if item.get("is_pano") is not True]
        if target:
            images = [found for item in images if (found := facing_target(item, target, max_heading_offset))]
        return {"source":"Mapillary","bbox":list(bbox),"images":images,
                "captured_after":captured_after.isoformat() if captured_after else None,
                "captured_before":captured_before.isoformat() if captured_before else None,
                "panoramas_excluded":0 if include_panoramas else panoramas,
                "target":list(target) if target else None, "max_heading_offset":max_heading_offset if target else None,
                "limit_reached":len(returned) >= limit,
                "has_more":bool(next_url),
                "note":"Discovery only; inspect dates, license, locations and both residential/commercial coverage before use."}
    except httpx.HTTPError:
        raise ValueError("Mapillary request failed; check connectivity and token") from None
    finally:
        if owned:
            client.close()


def target_bbox(target: tuple[float, float], radius_m: float) -> tuple[float, float, float, float]:
    """A small search box around a (lon, lat) target."""
    lon, lat = target
    dlat = radius_m / 110_540
    dlon = radius_m / (111_320 * math.cos(math.radians(lat)))
    return (lon-dlon, lat-dlat, lon+dlon, lat+dlat)


def capture_day(item: dict[str, Any]) -> date | None:
    value = item.get("captured_at")
    return datetime.fromtimestamp(value/1000, tz=timezone.utc).date() if isinstance(value, (int, float)) else None


def pair_candidates(before: list[dict[str, Any]], after: list[dict[str, Any]], max_distance_m: float = 15,
                    max_heading_difference: float = 30, min_gap: timedelta = timedelta(days=365)) -> list[dict[str, Any]]:
    """Match earlier and later images taken from nearly the same spot and direction, closest first."""
    pairs = []
    for old in before:
        for new in after:
            a, b = location(old), location(new)
            old_day, new_day = capture_day(old), capture_day(new)
            heading_a = old.get("computed_compass_angle", old.get("compass_angle"))
            heading_b = new.get("computed_compass_angle", new.get("compass_angle"))
            if (a is None or b is None or old_day is None or new_day is None or new_day - old_day < min_gap
                    or not isinstance(heading_a, (int, float)) or not isinstance(heading_b, (int, float))):
                continue
            distance = bearing_and_distance(a, b)[1]
            turn = abs((heading_a - heading_b + 180) % 360 - 180)
            if distance <= max_distance_m and turn <= max_heading_difference:
                pairs.append({"earlier_id": str(old["id"]), "later_id": str(new["id"]),
                              "earlier_date": old_day.isoformat(), "later_date": new_day.isoformat(),
                              "camera_distance_m": round(distance, 2), "heading_difference": round(turn, 1)})
    return sorted(pairs, key=lambda p: (p["camera_distance_m"], p["heading_difference"]))
