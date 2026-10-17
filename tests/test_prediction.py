import json
from datetime import date

import numpy as np
import pytest

from youseela.export import build_bundle
from youseela.fixtures import make_fixture
from youseela.prediction import attach, metrics
from youseela.prediction.business_model import category, cohort
from youseela.prediction.features import (majority_group, rent_pressure, top_quartile_labels, tract_rows, tract_zip_features,
                                          zip_features)
from youseela.scoring import load_config


def acs_row(rent: float, income: float, **extra: float) -> dict:
    return {"B01003_001E": 3000, "B25064_001E": rent, "B19013_001E": income, "B25077_001E": 500000, **extra}


def test_rent_pressure_and_top_quarter_labels() -> None:
    assert rent_pressure(acs_row(1000, 50000), acs_row(1300, 55000)) == pytest.approx(.2)
    assert rent_pressure(acs_row(1000, 50000), {"B25064_001E": "-666666666"}) is None
    labels, cutoff = top_quartile_labels({str(i): i / 10 for i in range(8)})
    assert cutoff == .6 and [g for g, v in labels.items() if v] == ["6", "7"]


def test_tract_rows_use_county_relative_values_trend_and_skip_tiny_tracts() -> None:
    acs = {"a": acs_row(1000, 50000, B03002_001E=1000, B03002_012E=600, B03002_004E=300),
           "b": acs_row(2000, 100000), "tiny": {**acs_row(1500, 70000), "B01003_001E": 50}}
    rows = tract_rows(acs, {"a": acs_row(800, 50000)}, {"a": {"amenity_density": 4.0}})
    assert "tiny" not in rows
    assert rows["a"]["rent_vs_county"] == pytest.approx(1000 / 1500)
    assert rows["a"]["pressure_prior"] == pytest.approx(.25)
    assert rows["a"]["hispanic_share"] == .6 and rows["a"]["amenity_density"] == 4.0
    assert rows["b"]["rent_growth_prior"] is None and rows["b"]["amenity_density"] is None
    assert majority_group(rows["a"]) == "Hispanic or Latino"


def test_zip_features_are_densities_and_area_weighted_onto_tracts() -> None:
    counts = {"90301": {"------": 100, "722515": 5, "722511": 15}, "90302": {"------": 50}}
    prior = {"90301": {"------": 90, "722515": 4, "722511": 15}}
    values = zip_features(counts, prior, {"90301": 10, "90302": 5})
    assert values["90301"]["amenity_density"] == 2 and values["90301"]["amenity_share"] == .2
    assert values["90301"]["amenity_growth"] == pytest.approx(np.log(21) - np.log(20))
    blended = tract_zip_features({"t": {"90301": .75, "90302": .25, "99999": .5}}, values)
    assert blended["t"]["establishment_density"] == pytest.approx(.75 * 10 + .25 * 10)


def test_ranking_metrics_and_bootstrap() -> None:
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    score = np.arange(10, 0, -1, dtype=float)
    assert metrics.precision_at(y, score, .2) == 1 and metrics.lift_at(y, score, .2) == 5
    result = metrics.evaluate(y, score / 10, probability=True, rounds=50)
    assert result["auc"] == 1 and result["positives"] == 2 and len(result["calibration"]) == 10


def test_business_types_come_from_names_and_labels_from_end_dates() -> None:
    assert category("TACOS EL GORDO") == "Food & drink" and category("Luxe Nail Spa") == "Personal services"
    assert category("SWEET ICE CREAM CO") == "Food & drink" and category("ACME HOLDINGS LLC") == "Other"
    rows = [{"name": "CORNER MARKET", "start": "2012-03-01", "end": "2017-06-01", "zip": "90001"},
            {"name": "CAFE", "start": "2014-06-30", "end": None, "zip": "90001"},
            {"name": "OLD SHOP", "start": "2001-01-01", "end": "2013-01-01", "zip": "90001"},
            {"name": "LATE SHOP", "start": "2016-01-01", "end": None, "zip": "90001"}]
    found = cohort(rows, date(2014, 12, 31), date(2019, 12, 31))
    assert [(r["name"], r["closed"], r["category"]) for r in found] == [("CORNER MARKET", 1, "Retail"), ("CAFE", 0, "Food & drink")]
    assert found[0]["age_years"] == pytest.approx(2.83, abs=.01)


def predictions_files(tmp_path, area_id: str):
    factor = {"feature": "rent_vs_county", "label": "Median rent relative to county", "effect": .1, "value": 1.2, "county_median": 1.0}
    tract = {"test_auc": .75, "test_precision_top10": .63, "test_base_rate": .25,
             "tracts": {area_id: {"probability": .6, "county_percentile": .9, "top_factors": [factor]}},
             "backtest": {"tracts": {area_id: {"probability": .3, "county_percentile": .6, "actual_pressure": .32,
                                               "actual_top_quarter": True, "top_factors": []}}}}
    business = {"test_auc": .59, "test_auc_consumer": .62, "test_businesses": 1000,
                "tracts": {area_id: {"zip": "90301", "by_type": {"Retail": {"new_business": .1, "typical": .07, "county_typical": .08}}}}}
    (tmp_path / "t.json").write_text(json.dumps(tract))
    (tmp_path / "b.json").write_text(json.dumps(business))
    return tmp_path / "t.json", tmp_path / "b.json"


def test_current_views_get_forecasts_and_historical_views_get_backtests(tmp_path) -> None:
    dataset = make_fixture(1)
    area_id = dataset.areas[0].id
    tract_path, business_path = predictions_files(tmp_path, area_id)
    current = attach.attach_predictions(dataset, date(2026, 10, 17), tract_path, business_path).areas[0].predictions
    assert [p.key for p in current] == ["rent_pressure_5yr", "business_closure_5yr"]
    assert current[0].tier == "higher" and current[0].kind == "forecast" and "0.75" in current[0].accuracy
    assert current[1].by_type["Retail"]["new_business"] == .1 and "ZIP 90301" in current[1].basis
    past = attach.attach_predictions(dataset, date(2020, 12, 31), tract_path, business_path).areas[0].predictions
    assert [p.kind for p in past] == ["backtest"] and "did reach" in past[0].outcome and past[0].tier == "moderate"
    bundle = build_bundle(attach.attach_predictions(dataset, date(2026, 10, 17), tract_path, business_path), load_config(), date(2026, 10, 17))
    assert bundle.areas[0].predictions[0].probability == .6


def test_partial_evidence_rates_from_census_and_says_so() -> None:
    dataset = make_fixture(3)
    strict = build_bundle(dataset, load_config(), date(2026, 10, 17))
    loose = build_bundle(dataset, load_config().model_copy(update={"allow_partial_evidence": True}), date(2026, 10, 17))
    for before, after in zip(strict.areas, loose.areas):
        for mode in ("housing", "commercial"):
            a, b = getattr(before, mode), getattr(after, mode)
            if a.status == "rated":
                assert b == a.model_copy(update={"basis": b.basis}) and "reviewed street-image" in b.basis
            elif after.indicators.rent_burden_share is not None:
                assert b.status == "rated" and b.basis.startswith("Rough score from Census data only")
                assert abs(sum(c.weight for c in b.contributions) - 1) < 1e-6
                assert "corroborated_visual_change" not in {c.feature for c in b.contributions}
            else:
                assert b.status == "insufficient_evidence"
