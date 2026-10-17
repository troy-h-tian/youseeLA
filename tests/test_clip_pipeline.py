from datetime import date

import pytest

from youseela.contracts import ClipPairFeature, Evidence, NumericalIndicators
from youseela.scoring import AssessmentConfig, assess
from youseela.vision.clip_features import embedding_difference


def pair() -> ClipPairFeature:
    return ClipPairFeature(id='pair', area_id='a', mode='commercial', site_id='site',
                           earlier_image_id='old', later_image_id='new', cosine_similarity=.6,
                           visual_difference=.2, model='ViT-B/32', model_revision='test',
                           image_sha256=['a'*64, 'b'*64])


def evidence() -> list[Evidence]:
    return [Evidence(id='census', area_id='a', kind='census', mode='both', reviewed=True,
                     source_date='2019-12-31', source_url='https://example.org/acs', attribution='Census', license='Public'),
            *[Evidence(id=id, area_id='a', kind='image', mode='commercial', site_id='site',
                       latitude=33.95, longitude=-118.35, source_date=day, source_url='https://example.org/'+id,
                       attribution='Photographer', license='CC BY-SA 4.0')
              for id,day in [('old','2019-05-20'),('new','2020-01-09')]]]


def test_embedding_difference_is_normalized_and_identical_is_zero() -> None:
    assert embedding_difference([1, 0], [3, 0]) == pytest.approx((1, 0))
    assert embedding_difference([1, 0], [0, 1]) == pytest.approx((0, .5))
    with pytest.raises(ValueError): embedding_difference([0, 0], [1, 0])
    with pytest.raises(ValueError): embedding_difference([1], [1, 2])


def test_clip_is_a_real_additive_scoring_input_without_human_change_labels() -> None:
    config = AssessmentConfig(visual_method='clip_pairs', minimum_pairs=1)
    numbers = NumericalIndicators(rent_burden_share=.5, affordability_pressure=.4, evidence_ids=['census'])
    result = assess('a', 'commercial', numbers, evidence(), config, date(2020,12,31), [pair()])
    assert result.status == 'rated'
    assert result.score == pytest.approx(39)
    assert result.contributions[-1].points == pytest.approx(4)
    unchanged = pair().model_copy(update={'cosine_similarity':1, 'visual_difference':0})
    baseline = assess('a', 'commercial', numbers, evidence(), config, date(2020,12,31), [unchanged])
    assert result.score - baseline.score == pytest.approx(4)
    assert not evidence()[1].reviewed


def test_missing_stale_wrong_mode_and_unmatched_pairs_do_not_score() -> None:
    config = AssessmentConfig(visual_method='clip_pairs')
    numbers = NumericalIndicators(rent_burden_share=.5, affordability_pressure=.4, evidence_ids=['census'])
    assert assess('a','commercial',numbers,evidence(),config,date(2020,12,31),[]).score is None
    assert assess('a','housing',numbers,evidence(),config,date(2020,12,31),[pair()]).score is None
    assert assess('a','commercial',numbers,evidence(),config,date(2026,12,31),[pair()]).score is None
    wrong = pair().model_copy(update={'later_image_id':'missing'})
    assert assess('a','commercial',numbers,evidence(),config,date(2020,12,31),[wrong]).score is None
