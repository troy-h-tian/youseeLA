import httpx
import pytest

from youseela.sources.imagery import discover_images


def test_image_discovery_keeps_credentials_out_of_saved_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "hidden-token" not in str(request.url)
        return httpx.Response(200,json={"data":[{"id":"123","captured_at":1700000000000,"geometry":{"coordinates":[-118.35,33.95]}}],"paging":{"next":"https://graph.mapillary.com?access_token=hidden-token"}})
    client=httpx.Client(transport=httpx.MockTransport(handler))
    result=discover_images((-118.36,33.95,-118.355,33.955),"hidden-token",client=client)
    assert result["has_more"] is True
    assert "hidden-token" not in str(result)


def test_imagery_without_key_or_oversized_box_fails_early() -> None:
    with pytest.raises(ValueError,match="MAPILLARY"):
        discover_images((-118.36,33.95,-118.355,33.955),"")
    with pytest.raises(ValueError,match="small"):
        discover_images((-120,30,-110,40),"key")


def test_capture_date_filter_is_sent_and_stale_results_are_excluded() -> None:
    from datetime import date
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params['start_captured_at'] == '2023-10-18T00:00:00Z'
        return httpx.Response(200, json={'data':[
            {'id':'old','captured_at':1576800000000},
            {'id':'recent','captured_at':1735689600000}
        ]})
    client=httpx.Client(transport=httpx.MockTransport(handler))
    result=discover_images((-118.36,33.95,-118.355,33.955),'key',client=client,captured_after=date(2023,10,18))
    assert [item['id'] for item in result['images']] == ['recent']
    assert result['captured_after'] == '2023-10-18'


def image(id: str, lon: float, lat: float, heading: float, day: str, pano: bool = False) -> dict:
    from datetime import datetime, timezone
    stamp = datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000
    return {"id": id, "captured_at": stamp, "computed_geometry": {"type": "Point", "coordinates": [lon, lat]},
            "computed_compass_angle": heading, "is_pano": pano}


def test_targeted_discovery_drops_panoramas_and_cameras_facing_away() -> None:
    from datetime import date
    # Target is 0.0005 degrees north (about 55 m) of every camera, so facing it means a heading near 0.
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["end_captured_at"] == "2019-01-01T00:00:00Z"
        assert "is_pano" in request.url.params["fields"]
        return httpx.Response(200, json={"data": [image("facing", -118.35, 33.9665, 10, "2018-05-01"),
                                                  image("away", -118.35, 33.9665, 180, "2018-05-01"),
                                                  image("pano", -118.35, 33.9665, 0, "2018-05-01", pano=True),
                                                  image("late", -118.35, 33.9665, 0, "2019-06-01")]})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = discover_images((-118.351, 33.966, -118.349, 33.968), "key", client=client,
                             captured_before=date(2019, 1, 1), target=(-118.35, 33.967))
    assert [item["id"] for item in result["images"]] == ["facing"]
    assert result["images"][0]["heading_offset"] == 10 and 50 < result["images"][0]["target_distance_m"] < 60
    assert result["panoramas_excluded"] == 1


def test_pages_are_followed_only_when_requested_and_links_are_not_saved() -> None:
    calls = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        page = 2 if "after=" in str(request.url) else 1
        return httpx.Response(200, json={"data": [{"id": f"p{page}-{i}"} for i in range(2)],
                                         "paging": {"next": "https://graph.mapillary.com/images?after=abc&access_token=secret"} if page == 1 else {}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = discover_images((-118.36, 33.95, -118.355, 33.955), "key", limit=2, client=client, max_pages=3)
    assert [i["id"] for i in result["images"]] == ["p1-0", "p1-1", "p2-0", "p2-1"]
    assert len(calls) == 2 and result["has_more"] is False and "secret" not in str(result)


def test_pairs_need_same_spot_direction_and_a_year_apart() -> None:
    from youseela.sources.imagery import pair_candidates
    before = [image("old", -118.35, 33.9665, 10, "2018-05-01")]
    after = [image("same", -118.35003, 33.9665, 20, "2023-05-01"),      # about 3 m away, 10 degrees turned
             image("turned", -118.35, 33.9665, 100, "2023-05-01"),
             image("far", -118.3495, 33.9665, 10, "2023-05-01"),
             image("soon", -118.35, 33.9665, 10, "2018-09-01")]
    pairs = pair_candidates(before, after)
    assert [(p["earlier_id"], p["later_id"]) for p in pairs] == [("old", "same")]
    assert pairs[0]["camera_distance_m"] < 4
