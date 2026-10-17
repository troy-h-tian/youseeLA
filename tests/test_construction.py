from youseela.construction import construction_sites, public_image


def test_sites_group_recent_builds_by_map_page_inside_the_tract() -> None:
    tract = {"type": "Polygon", "coordinates": [[[0, 0], [.01, 0], [.01, .01], [0, .01], [0, 0]]]}
    def parcel(ain: str, built: str, lon: float = .005, taxable: str = "Y") -> dict:
        return {"AIN": ain, "RollYear": "2025", "isTaxableParcel": taxable, "EffectiveYearBuilt": built,
                "CENTER_LAT": .005, "CENTER_LON": lon}
    parcels = [parcel("4015024001", "2021"), parcel("4015024002", "2022", lon=.0051), parcel("4015024002", "2022"),
               parcel("4015024003", "1950"), parcel("4015025001", "2023", taxable="N"), parcel("4015026001", "2020", lon=.5)]
    sites = construction_sites(parcels, tract, 2019, 2025, 2025)
    assert [(s["site_id"], s["parcels"], s["years_built"]) for s in sites] == [("assessor-page-4015024", 2, [2021, 2022])]
    assert 0 < sites[0]["extent_m"] < 10


def test_public_image_drops_signed_thumbnail_urls() -> None:
    item = public_image({"id": "123", "thumb_1024_url": "https://scontent.example/x?oh=signed", "creator": {"username": "u"}})
    assert item["url"] == "https://www.mapillary.com/app/?pKey=123" and item["creator"] == "u"
    assert "signed" not in str(item)
