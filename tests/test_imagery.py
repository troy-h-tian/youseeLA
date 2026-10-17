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
