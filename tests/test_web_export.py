from datetime import date

from youseela.export import build_bundle
from youseela.fixtures import make_fixture
from youseela.scoring import load_config
from youseela.web_export import to_web_bundle


def test_web_adapter_preserves_scores_missing_values_and_provenance() -> None:
    source = build_bundle(make_fixture(3), load_config(), date(2026, 10, 17))
    result = to_web_bundle(source)
    assert result['schema_version'] == 1
    assert result['data_kind'] == 'fixture'
    for original, area in zip(source.areas, result['areas']):
        assert area['boundary'] == original.geometry
        for mode in ['housing', 'commercial']:
            assessment = area[mode]
            before = getattr(original, mode)
            assert assessment['score'] == before.score
            assert assessment['tier'] == before.tier
            if before.status == 'insufficient_evidence':
                assert assessment['unrated_reason']
                assert assessment['contributions'] == []
                assert set(original.indicators.evidence_ids) <= set(assessment['evidence_ids'])
    assert result['businesses'][0]['location']['lat'] == source.businesses[0].latitude
    assert result['methodology']['tier_bands']['moderate_below'] == 67


def test_web_adapter_does_not_invent_visible_work_counts() -> None:
    source = build_bundle(make_fixture(1), load_config(), date(2026, 10, 17))
    result = to_web_bundle(source)
    observations = [o for e in result['evidence'] for o in e['observations']]
    assert observations
    assert all(o['visible_count'] is None for o in observations)
