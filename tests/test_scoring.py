from datetime import date

import pytest

from youseela.contracts import Evidence, NumericalIndicators
from youseela.scoring import assess, load_config


def evidence(area: str = "a", mode: str = "housing", active: bool = True) -> list[Evidence]:
    items = [Evidence(id=f"{area}-acs", area_id=area, kind="census", mode="both", source_url="https://example.org/acs", source_date=date(2024, 12, 31), attribution="Synthetic fixture", license="fixture", reviewed=True, data_kind="fixture")]
    items.append(Evidence(id=f"{area}-project", area_id=area, kind="project", mode="both", source_url="https://example.org/project", source_date=date(2025, 1, 1), attribution="Synthetic fixture", license="fixture", reviewed=True, data_kind="fixture", applies_to_site_ids=[f"site-{site}" for site in range(3)]))
    for site in range(3):
        items.append(Evidence(id=f"{area}-{mode}-{site}", area_id=area, kind="image", mode=mode, source_url="https://example.org/image", source_date=date(2026, 1, 1), attribution="Synthetic fixture", license="fixture", reviewed=True, data_kind="fixture", site_id=f"site-{site}", latitude=33.95 + site * .001, longitude=-118.35, observations=[{"frontage_id": f"{mode}-{site}-{front}", "redevelopment": "present" if active else "absent", "corroboration_ids": [f"{area}-project"] if active else [], "description": "Synthetic visible construction" if active else "Synthetic unobstructed frontage"} for front in range(2)]))
    return items


def indicators(pressure: float | None = 0.5) -> NumericalIndicators:
    return NumericalIndicators(rent_burden_share=0.5, affordability_pressure=pressure, evidence_ids=["a-acs"])


def test_housing_image_features_change_explained_score() -> None:
    config = load_config()
    result = assess("a", "housing", indicators(), evidence(), config, date(2026, 10, 17))
    without = assess("a", "housing", indicators(), evidence(active=False), config, date(2026, 10, 17))
    assert result.status == "rated"
    assert result.score == pytest.approx(50)
    assert result.score - without.score == pytest.approx(7.5)
    assert sum(c.points for c in result.contributions) == pytest.approx(result.score)


def test_missing_images_does_not_become_low_risk() -> None:
    result = assess("a", "housing", indicators(), [], load_config(), date(2026, 10, 17))
    assert result.status == "insufficient_evidence"
    assert result.score is None and result.tier is None


def test_ambiguous_pressure_is_unrated() -> None:
    assert assess("a", "housing", indicators(None), evidence(), load_config(), date(2026, 10, 17)).score is None


def test_commercial_photos_cannot_satisfy_housing_coverage() -> None:
    assert assess("a", "housing", indicators(), evidence(mode="commercial"), load_config(), date(2026, 10, 17)).score is None


def test_repeated_sites_and_unconfirmed_work_do_not_pass_gate() -> None:
    items = evidence()
    for item in items:
        if item.kind == "image":
            item.site_id = "same-site"
    assert assess("a", "housing", indicators(), items, load_config(), date(2026, 10, 17)).score is None
    items = [item for item in evidence() if item.kind != "project"]
    assert assess("a", "housing", indicators(), items, load_config(), date(2026, 10, 17)).score is None


def test_images_alone_do_not_add_risk_without_affordability_change() -> None:
    config = load_config()
    yes = assess("a", "housing", indicators(0), evidence(), config, date(2026, 10, 17))
    no = assess("a", "housing", indicators(0), evidence(active=False), config, date(2026, 10, 17))
    assert yes.score == no.score == 30


def test_stale_images_and_future_dates_are_not_current_evidence() -> None:
    for day in [date(2010, 1, 1), date(2030, 1, 1)]:
        items = evidence()
        for item in items:
            if item.kind == "image":
                item.source_date = day
        assert assess("a", "housing", indicators(), items, load_config(), date(2026, 10, 17)).score is None


def test_project_at_another_site_cannot_corroborate_images() -> None:
    items = evidence()
    project = next(item for item in items if item.kind == "project")
    project.site_id = "unrelated-site"
    assert assess("a", "housing", indicators(), items, load_config(), date(2026, 10, 17)).score is None


def test_historical_corroboration_is_not_counted_as_current_sample() -> None:
    items = evidence()
    current = next(item for item in items if item.kind == "image")
    historical = current.model_copy(deep=True)
    historical.id = "historical-image"
    historical.source_date = date(2025, 1, 1)
    for observation in historical.observations:
        observation.redevelopment = "absent"
        observation.corroboration_ids = []
    for observation in current.observations:
        observation.corroboration_ids = [historical.id]
    items.append(historical)
    result = assess("a", "housing", indicators(), items, load_config(), date(2026, 10, 17))
    assert result.status == "rated"
    assert result.coverage.images == 3
    assert historical.id in result.evidence_ids


def test_empty_photos_cannot_satisfy_minimum_sites() -> None:
    items = evidence(active=False)
    images = [item for item in items if item.kind == "image"]
    images[0].observations = [observation for image in images for observation in image.observations]
    images[1].observations = []
    images[2].observations = []
    result = assess("a", "housing", indicators(), items, load_config(), date(2026, 10, 17))
    assert result.score is None
    assert result.coverage.sites == 1


def test_invalid_history_reference_cannot_hide_ambiguous_current_image() -> None:
    items = evidence()
    unclear = items[-1].model_copy(deep=True)
    unclear.id = "unclear-current"
    unclear.observations[0].redevelopment = "unclear"
    items.append(unclear)
    unrelated = unclear.model_copy(deep=True)
    unrelated.id = "unrelated-old-commercial"
    unrelated.mode = "commercial"
    unrelated.source_date = date(2025, 1, 1)
    for observation in unrelated.observations:
        observation.redevelopment = "absent"
        observation.corroboration_ids = [unclear.id]
    items.append(unrelated)
    assert assess("a", "housing", indicators(), items, load_config(), date(2026, 10, 17)).score is None


def test_uncertainty_range_preserves_point_and_image_contribution() -> None:
    inputs = NumericalIndicators.model_validate({**indicators().model_dump(), 'affordability_pressure_range': {'lower':0.0, 'upper':1.0}})
    result = assess('a', 'housing', inputs, evidence(), load_config(), date(2026,10,17))
    assert result.score == 50
    assert result.score_range.lower == 30
    assert result.score_range.upper == 70
    missing = assess('a', 'housing', inputs, [], load_config(), date(2026,10,17))
    assert missing.score is None and missing.score_range is None
