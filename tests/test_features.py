from youseela.features import affordability_pressure, rent_burden_share, renter_share


def test_rent_burden_uses_household_counts_not_median_ratios() -> None:
    row = {"B25070_001E": "100", "B25070_011E": "10", "B25070_007E": "10",
           "B25070_008E": "10", "B25070_009E": "10", "B25070_010E": "15"}
    assert rent_burden_share(row) == 0.5


def test_invalid_or_suppressed_counts_are_missing() -> None:
    assert rent_burden_share({}) is None
    assert renter_share({"B25003_001E": "0", "B25003_003E": "0"}) is None
    assert renter_share({"B25003_001E": "10", "B25003_003E": "11"}) is None
    assert renter_share({"B25003_001E": "10", "B25003_003E": "-666666666"}) is None


def test_affordability_pressure_requires_clear_direction() -> None:
    old = {"B25064_001E": "1000", "B25064_001M": "10", "B19013_001E": "50000", "B19013_001M": "100"}
    new = {"B25064_001E": "1300", "B25064_001M": "10", "B19013_001E": "55000", "B19013_001M": "100"}
    result = affordability_pressure(old, new)
    assert result.value is not None and abs(result.value - 1.0) < 1e-9
    assert result.lower_bound is not None and result.lower_bound > 0
    assert affordability_pressure(old, old).value is None
    assert affordability_pressure({}, new).value is None


def test_uncertain_pressure_can_be_preserved_for_sensitivity_display() -> None:
    old = {'B25064_001E':'1000', 'B25064_001M':'100', 'B19013_001E':'50000', 'B19013_001M':'5000'}
    result = affordability_pressure(old, old, allow_uncertain=True)
    assert result.value == 0
    assert result.lower_bound < 0 < result.upper_bound
    assert affordability_pressure({}, old, allow_uncertain=True).value is None
