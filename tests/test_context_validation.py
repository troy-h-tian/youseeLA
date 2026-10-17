import math

import pytest

from youseela import context_validation as cv


def square(size: float = 1) -> dict:
    return {"type": "Polygon", "coordinates": [[[0, 0], [size, 0], [size, size], [0, size], [0, 0]]]}


def test_auc_counts_ties_as_half() -> None:
    assert cv.auc([3, 4], [1, 2]) == 1
    assert cv.auc([1, 2], [3, 4]) == 0
    assert cv.auc([1], [1]) == .5


def test_bootstrap_interval_is_reproducible_and_ordered() -> None:
    positive, negative = [.2, .3, .25, .4, .35], [.1, .15, .3, .12, .2]
    first = cv.bootstrap_interval(positive, negative, seed=1, rounds=500)
    assert first == cv.bootstrap_interval(positive, negative, seed=1, rounds=500)
    assert 0 <= first[0] <= cv.auc(positive, negative) <= first[1] <= 1


def test_sample_is_seeded_balanced_and_excludes_study_area() -> None:
    udp = {f"06037{i:06d}": ("EOG" if i % 3 == 0 else "LISD" if i % 3 == 1 else "SAE") for i in range(60)}
    udp["06059000001"] = "EOG"  # Orange County must never be sampled
    excluded = "06037000000"
    sample = cv.sample_tracts(udp, {excluded}, 5, seed=7)
    assert sample == cv.sample_tracts(udp, {excluded}, 5, seed=7)
    assert sorted(sample.values()).count("gentrifying") == 5 and len(sample) == 10
    assert excluded not in sample and "06059000001" not in sample
    assert all(udp[g] in {"EOG", "LISD"} for g in sample)
    with pytest.raises(ValueError, match="Only"):
        cv.sample_tracts(udp, set(), 100, seed=7)


def test_tract_metrics_use_recent_residential_sales_inside_the_tract() -> None:
    parcels = [{"AIN": str(i), "RollYear": "2018", "isTaxableParcel": "Y", "UseType": "SFR",
                "Roll_LandBaseYear": "2016" if i < 20 else "1990", "EffectiveYearBuilt": "2017" if i < 5 else "1950",
                "SQFTmain": 1000, "Roll_totLandImp": 500_000 if i < 20 else 100_000, "CENTER_LAT": .5, "CENTER_LON": .5}
               for i in range(100)]
    parcels.append({**parcels[0], "AIN": "outside", "CENTER_LON": 5})
    result = cv.tract_metrics(parcels, square(), 2018)
    assert result["taxable"] == 100
    assert result["reassessed_share"] == .2 and result["built_or_renovated_share"] == .05
    assert result["recent_sales"] == 20 and result["recent_sale_value_per_sqft"] == 500


def test_indicators_withhold_missing_inputs() -> None:
    early = {"reassessed_share": .1, "built_or_renovated_share": None, "recent_sale_value_per_sqft": 200}
    late = {"reassessed_share": .15, "built_or_renovated_share": .01, "recent_sale_value_per_sqft": 400}
    result = cv.indicators(early, late)
    assert result["reassessed_share_change"] == pytest.approx(.05)
    assert result["built_or_renovated_share_change"] is None
    assert result["recent_sale_value_growth"] == pytest.approx(math.log(2))


def test_compare_flags_circular_price_signal_and_small_groups() -> None:
    rows = [{"group": "gentrifying" if i < 12 else "comparison",
             "indicators": {"reassessed_share": i / 30, "reassessed_share_change": None, "built_or_renovated_share": 0,
                            "built_or_renovated_share_change": 0, "recent_sale_value_growth": 1 - i / 30}} for i in range(24)]
    result = cv.compare(rows, seed=1)
    assert result["reassessed_share"]["auc"] == 0
    assert result["recent_sale_value_growth"]["auc"] == 1 and "circularity" in result["recent_sale_value_growth"]
    assert result["reassessed_share_change"]["auc"] is None
