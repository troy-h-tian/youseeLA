import io
import zipfile
from datetime import date, datetime, timezone

import httpx
import pytest
from pydantic import ValidationError

from youseela import context as ctx
from youseela.contracts import ContextIndicator
from youseela.export import build_bundle
from youseela.fixtures import make_fixture
from youseela.scoring import load_config
from youseela.sources import assessor, business, typology
from youseela.web_export import to_web_bundle


def square(x: float, y: float = 0, size: float = 1) -> dict:
    return {"type": "Polygon", "coordinates": [[[x, y], [x+size, y], [x+size, y+size], [x, y+size], [x, y]]]}


def test_udp_restores_leading_zero_and_skips_combined_categories() -> None:
    text = 'GEOID,typ_cat\n6037601900,"[\'OD\']"\n6037602200.0,"[\'AdvG\', \'BE\']"\n6037600100,[]\n'
    assert typology.parse_udp(text) == {"06037601900": "OD"}


def test_split_tracts_get_no_benchmark_label() -> None:
    rows = {"A": [{"tract10": "old", "part": 98, "land20": 100, "land10": 100}],
            "B": [{"tract10": "big", "part": 53, "land20": 100, "land10": 60},
                  {"tract10": "other", "part": 47, "land20": 100, "land10": 47}]}
    assert typology.equivalent_2010_tract("A", rows) == "old"
    assert typology.equivalent_2010_tract("B", rows) is None
    assert typology.equivalent_2010_tract("missing", rows) is None


def test_tract_activity_counts_only_taxable_parcels_inside_the_window() -> None:
    def parcel(ain: str, lon: float, base: str, built: str = "1950", taxable: str = "Y") -> dict:
        return {"AIN": ain, "RollYear": "2025", "isTaxableParcel": taxable, "Roll_LandBaseYear": base,
                "EffectiveYearBuilt": built, "CENTER_LAT": .5, "CENTER_LON": lon}
    parcels = [parcel("1", .5, "2021"), parcel("2", .5, "2020", built="2023"), parcel("2", .5, "2022"),
               parcel("3", .5, "2024", taxable="N"), parcel("4", 1.5, "1975"), parcel("5", 9, "2024")]
    counts = assessor.tract_activity(parcels, {"a": square(0), "b": square(1)}, 2025)
    assert counts["a"] == {"taxable": 2, "reassessed": 1, "built_or_renovated": 1}
    assert counts["b"] == {"taxable": 1, "reassessed": 0, "built_or_renovated": 0}


def test_parcel_paging_retries_transient_service_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assessor, "PAGE", 2)
    monkeypatch.setattr(assessor.time, "sleep", lambda _: None)
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = request.url.params["resultOffset"]
        calls.append(offset)
        if offset == "2" and calls.count("2") == 1:
            return httpx.Response(200, json={"error": {"code": 504}})
        rows = {"0": [1, 2], "2": [3]}[offset]
        return httpx.Response(200, json={"features": [{"attributes": {"AIN": str(r)}} for r in rows],
                                         "exceededTransferLimit": offset == "0"})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    parcels = assessor.fetch_parcels(2025, (-118.4, 33.9, -118.3, 34.0), client=client)
    assert [p["AIN"] for p in parcels] == ["1", "2", "3"]
    assert calls == ["0", "2", "2"]


def test_parcel_fetch_reports_persistent_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(assessor.time, "sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"error": {"code": 500}})))
    with pytest.raises(ValueError, match="service error 500"):
        assessor.fetch_parcels(2025, (-118.4, 33.9, -118.3, 34.0), client=client, retries=1)
    with pytest.raises(ValueError, match="2006 through 2025"):
        assessor.service_url(2030)


def test_small_tracts_withhold_shares() -> None:
    found, evidence = ctx.assessor_context({"a": {"taxable": 10, "reassessed": 5, "built_or_renovated": 1},
                                            "b": {"taxable": 100, "reassessed": 25, "built_or_renovated": 3}}, 2025, "latest")
    assert [c.value for c in found["a"]] == [None, None]
    assert [c.value for c in found["b"]] == [.25, .03]
    assert {e.kind for e in evidence} == {"assessor"} and all(e.reviewed for e in evidence)


def test_zbp_missing_codes_count_as_zero(tmp_path) -> None:
    rows = ['"zip","name","naics","est"', '"90301","INGLEWOOD, CA","------",817',
            '"90301","INGLEWOOD, CA","722515",5', '"90301","INGLEWOOD, CA","722511",18', '"90302","X","722515",3']
    path = tmp_path / "zbp.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("zbp19detail.txt", "\n".join(rows))
    counts = business.read_zbp(path, {"90301"})
    assert counts == {"90301": {"------": 817, "722515": 5, "722511": 18}}
    assert business.amenity_count(counts["90301"]) == 23


def test_tracts_map_to_the_zcta_covering_most_area() -> None:
    zctas = [{"properties": {"ZCTA5": "90301"}, "geometry": square(0, size=.7)},
             {"properties": {"ZCTA5": "90302"}, "geometry": square(.7, size=2)}]
    result = business.dominant_zctas({"t": square(0), "outside": square(5)}, zctas)
    # 90301 covers .7 x .7 of the unit tract; 90302 covers only the .3-wide strip beside it.
    assert result["t"][0] == "90301" and result["t"][1] == pytest.approx(.49)
    assert "outside" not in result


def test_share_indicators_must_be_fractions() -> None:
    with pytest.raises(ValidationError):
        ContextIndicator(key="k", label="l", value=1.5, unit="share", period="p", evidence_ids=["e"])


def fixture_with_context() -> tuple:
    dataset = make_fixture(2)
    area_id = dataset.areas[0].id
    found, evidence = ctx.assessor_context({area_id: {"taxable": 100, "reassessed": 30, "built_or_renovated": 4}}, 2025, "latest")
    zbp, zbp_evidence = ctx.business_context({area_id: ("90301", .9)}, {"90301": {"722515": 10}}, 2023, "latest")
    labels, udp_evidence = ctx.typology_context([area_id], {"06037000000": "OD"},
                                                {area_id: [{"tract10": "06037000000", "part": 100, "land20": 100, "land10": 100}]})
    context = ctx.ContextFile(generated_at=datetime.now(timezone.utc), sources={},
                              areas={area_id: ctx.AreaContext(context=found[area_id] + zbp[area_id],
                                                              reference_typology=labels[area_id]),
                                     "unknown-area": ctx.AreaContext()},
                              evidence=evidence + zbp_evidence + udp_evidence)
    return dataset, ctx.attach(dataset, context), area_id


def test_context_never_changes_scores_and_references_validate() -> None:
    dataset, attached, area_id = fixture_with_context()
    before = build_bundle(dataset, load_config(), date(2026, 10, 17))
    after = build_bundle(attached, load_config(), date(2026, 10, 17))
    for old, new in zip(before.areas, after.areas):
        for mode in ["housing", "commercial"]:
            assert getattr(old, mode) == getattr(new, mode)
    area = next(a for a in after.areas if a.id == area_id)
    assert area.reference_typology and area.reference_typology.code == "OD"
    assert {c.key for c in area.context} == {"reassessed_share_latest", "built_or_renovated_share_latest", "amenity_establishments_latest"}
    assert len(after.evidence) == len(before.evidence) + 3


def test_web_export_lists_context_and_filters_evidence_by_mode() -> None:
    _, attached, area_id = fixture_with_context()
    web = to_web_bundle(build_bundle(attached, load_config(), date(2026, 10, 17)))
    area = next(a for a in web["areas"] if a["id"] == area_id)
    keys = {i["key"] for i in area["indicators"]}
    assert {"reassessed_share_latest", "amenity_establishments_latest"} <= keys
    assert area["reference_typology"]["code"] == "OD"
    assert f"zbp-2023-{area_id}" in area["commercial"]["evidence_ids"]
    assert f"zbp-2023-{area_id}" not in area["housing"]["evidence_ids"]
    assert f"udp-2018-{area_id}" in area["housing"]["evidence_ids"]
    types = {e["evidence_type"] for e in web["evidence"]}
    assert {"assessor_roll", "business_patterns", "reference_typology"} <= types


def test_benchmark_groups_by_reference_and_lists_unmatched() -> None:
    _, attached, area_id = fixture_with_context()
    areas = {a.id: ctx.AreaContext(context=a.context, reference_typology=a.reference_typology) for a in attached.areas}
    result = ctx.benchmark(areas)
    assert result["groups"]["OD"]["medians"]["reassessed_share_latest"] == .3
    assert result["tracts_without_reference"] == sorted(a.id for a in attached.areas if a.id != area_id)


def test_overlapping_assessor_windows_are_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="overlap"):
        ctx.collect({"features": []}, tmp_path, 2022, 2025, 2019, 2023)
