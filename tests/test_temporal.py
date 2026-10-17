import json
import base64
from pathlib import Path

import httpx
import pytest

from youseela.vision.temporal import PairJob, compare_pair
from youseela.vision.provider import VisionSettings


def make_job(tmp_path: Path) -> PairJob:
    for name in ('old.jpg', 'new.jpg'):
        (tmp_path/name).write_bytes(b'\xff\xd8'+name.encode())
    return PairJob(id='pair', earlier_path=tmp_path/'old.jpg', later_path=tmp_path/'new.jpg',
                   earlier_date='2019-05-20', later_date='2020-01-09', analysis_permitted=True,
                   cache_permitted=True)


def test_pair_sends_both_images_in_order_and_caches(tmp_path: Path) -> None:
    calls = []
    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        content = body['input'][0]['content']
        images = [p for p in content if p['type'] == 'input_image']
        assert len(images) == 2
        assert base64.b64decode(images[0]['image_url'].split(',')[1]) == b'\xff\xd8old.jpg'
        assert base64.b64decode(images[1]['image_url'].split(',')[1]) == b'\xff\xd8new.jpg'
        assert '2019-05-20' in content[0]['text'] and '2020-01-09' in content[0]['text']
        calls.append(body)
        return httpx.Response(200, json={'status':'completed', 'usage':{}, 'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'comparability':'partial','matching_landmarks':['parking structure'],'observations':[{'location':'Left building','category':'no_clear_change','earlier_evidence':'Same floors visible','later_evidence':'Same floors visible','interpretation':'No clear structural change visible'}],'limitations':['Framing differs']})}]}]})
    config = VisionSettings(provider='openai', model='test', api_key='secret', budget_usd=.05, max_cost_per_request_usd=.05)
    job = make_job(tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(respond))
    first = compare_pair(job, config, tmp_path/'state', client)
    second = compare_pair(job, config, tmp_path/'state', client)
    assert first == second and len(calls) == 1
    assert not first.human_reviewed
    assert first.findings.comparability == 'partial'
    assert json.loads((tmp_path/'state'/'budget.json').read_text())['requests'] == 1
    job.id = 'uncached-pair'
    with pytest.raises(ValueError, match='budget'):
        compare_pair(job, config, tmp_path/'state', client)
    assert len(calls) == 1


def test_pair_rejects_reversed_dates_and_unpermitted_input(tmp_path: Path) -> None:
    job = make_job(tmp_path)
    with pytest.raises(ValueError, match='earlier'):
        PairJob.model_validate({**job.model_dump(), 'earlier_date':'2021-01-01'})
    job.analysis_permitted = False
    config = VisionSettings(provider='openai', model='test', api_key='secret', budget_usd=5, max_cost_per_request_usd=.05)
    with pytest.raises(ValueError, match='permission'):
        compare_pair(job, config, tmp_path/'state')
    assert not (tmp_path/'state'/'budget.json').exists()


def test_published_pair_matches_analyzed_image_bytes_and_dates() -> None:
    import hashlib
    from youseela.vision.temporal import PairResult
    root = Path(__file__).resolve().parents[1]
    result = PairResult.model_validate_json((root/'data/exports/temporal-comparison.json').read_text())
    panel = json.loads((root/'web/src/data/historical-comparison.json').read_text())
    assert panel['result'] == result.model_dump(mode='json')
    assert panel['historical_only'] is True
    for index, side in enumerate(('old', 'new')):
        photo = panel['pair'][side]
        image = root/'web/public'/photo['image_url']
        assert hashlib.sha256(image.read_bytes()).hexdigest() == result.image_sha256[index]
        assert photo['date'] == str(result.earlier_date if index == 0 else result.later_date)
        assert photo['attribution'] and photo['license'] == 'CC-BY-SA 4.0'
