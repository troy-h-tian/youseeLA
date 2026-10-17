import httpx
import pytest

from youseela.sources.census import CensusAccessError, fetch_county, parse_table
from youseela.sources.geography import intersecting_tracts


def test_census_tables_keep_full_geoid() -> None:
    rows = parse_table([["NAME", "state", "county", "tract"], ["Area", "06", "037", "600100"]])
    assert rows["06037600100"]["NAME"] == "Area"


def test_census_html_key_error_is_actionable_and_redacted() -> None:
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text="<html>Missing Key</html>")))
    with pytest.raises(CensusAccessError, match="CENSUS_API_KEY") as error:
        fetch_county(2024, "hidden-secret", client=client)
    assert "hidden-secret" not in str(error.value)


def test_missing_key_never_triggers_network_call() -> None:
    with pytest.raises(CensusAccessError):
        fetch_county(2024, "")


def test_tracts_touching_city_boundary_only_are_excluded() -> None:
    def square(x: float) -> dict:
        return {"type": "Polygon", "coordinates": [[[x,0],[x+1,0],[x+1,1],[x,1],[x,0]]]}
    city = square(0)
    features = [{"type":"Feature", "properties":{"GEOID":"inside"}, "geometry":square(0)},
                {"type":"Feature", "properties":{"GEOID":"touch"}, "geometry":square(1)}]
    assert [f["properties"]["GEOID"] for f in intersecting_tracts(city, features)] == ["inside"]
