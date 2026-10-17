from datetime import date

import pytest
from pydantic import ValidationError

from youseela.contracts import Bundle
from youseela.export import build_bundle
from youseela.fixtures import make_fixture
from youseela.scoring import load_config


def test_fixture_covers_rated_partial_and_unrated_frontend_states() -> None:
    bundle = build_bundle(make_fixture(3), load_config(), date(2026, 10, 17))
    assert bundle.data_kind == "fixture"
    assert bundle.areas[0].housing.status == "rated"
    assert bundle.areas[1].housing.status == "insufficient_evidence"
    assert bundle.areas[1].commercial.status == "rated"
    assert bundle.areas[2].commercial.status == "insufficient_evidence"
    assert Bundle.model_validate_json(bundle.model_dump_json()).schema_version == "1.0"


def test_fixture_cannot_masquerade_as_real() -> None:
    dataset = make_fixture(3)
    dataset.data_kind = "real"
    with pytest.raises(ValueError, match="Fixture"):
        build_bundle(dataset, load_config(), date(2026, 10, 17))


def test_dangling_evidence_and_geometry_mismatch_are_rejected() -> None:
    dataset = make_fixture(3)
    dataset.areas[0].indicators.evidence_ids = ["does-not-exist"]
    with pytest.raises(ValueError, match="evidence"):
        build_bundle(dataset, load_config(), date(2026, 10, 17))
    dataset = make_fixture(3)
    dataset.businesses[0].longitude = 0
    with pytest.raises(ValueError, match="outside"):
        build_bundle(dataset, load_config(), date(2026, 10, 17))


def test_export_does_not_silently_drop_unreviewed_evidence() -> None:
    dataset = make_fixture(3)
    dataset.evidence[0].reviewed = False
    with pytest.raises(ValueError, match="reviewed"):
        build_bundle(dataset, load_config(), date(2026, 10, 17))
