import pytest
from pydantic import ValidationError

from youseela.contracts import Assessment, Evidence


def test_unrated_assessment_cannot_have_a_score() -> None:
    with pytest.raises(ValidationError):
        Assessment(mode="housing", status="insufficient_evidence", score=0, tier="lower", reasons=["Missing images"])


def test_public_sources_cannot_embed_credentials() -> None:
    with pytest.raises(ValidationError):
        Evidence(id="x", area_id="a", kind="census", mode="both", source_url="https://example.org/?key=secret", source_date="2024-01-01", attribution="Census", license="Public domain", reviewed=True)


def test_nan_score_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Assessment(mode="housing", status="rated", score=float("nan"), tier="lower")
