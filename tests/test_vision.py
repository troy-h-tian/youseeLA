import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from youseela.contracts import Evidence
from youseela.vision.provider import ImageJob, VisionSettings, extract_image


PNG = bytes.fromhex("89504e470d0a1a0a") + b"test-fixture"


def job(tmp_path: Path) -> ImageJob:
    path = tmp_path / "sample.png"
    path.write_bytes(PNG)
    return ImageJob(image_path=path, analysis_permitted=True, cache_permitted=True,
                    evidence=Evidence(id="image-1", area_id="area", kind="image", mode="housing",
                                      source_url="https://example.org/image", source_date=date(2026,1,1),
                                      attribution="Fixture", license="Fixture", site_id="site-1", latitude=33.95, longitude=-118.35))


def settings() -> VisionSettings:
    return VisionSettings(provider="openai", model="test-model", api_key="hidden-key", budget_usd=.10, max_cost_per_request_usd=.06)


def response(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"status":"completed", "usage":{"input_tokens":100,"output_tokens":30},
                                    "output":[{"type":"message","content":[{"type":"output_text", "text":json.dumps({"frontages":[{"label":"Left frontage", "visible_work":"present", "description":"Scaffolding is visible"}]})}]}]})


def test_vision_reserves_budget_and_cache_does_not_spend_again(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []
    def transport(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return response(request)
    client = httpx.Client(transport=httpx.MockTransport(transport))
    work = job(tmp_path)
    first = extract_image(work, settings(), tmp_path/"state", client=client)
    second = extract_image(work, settings(), tmp_path/"state", client=client)
    assert len(calls) == 1
    assert first == second
    assert not first.reviewed
    assert first.observations[0].corroboration_ids == []
    work.evidence.id = "different-image"
    work.evidence.site_id = "different-site"
    with pytest.raises(ValueError, match="budget"):
        extract_image(work, settings(), tmp_path/"state", client=client)
    logs = (tmp_path/"state"/"telemetry.jsonl").read_text()
    assert "hidden-key" not in logs and "input_tokens" in logs and "cache_hit" in logs


def test_permissions_and_zero_budget_stop_before_network(tmp_path: Path) -> None:
    work = job(tmp_path)
    work.analysis_permitted = False
    with pytest.raises(ValueError, match="permission"):
        extract_image(work, settings(), tmp_path/"state")
    work.analysis_permitted = True
    config = settings()
    config.budget_usd = 0
    with pytest.raises(ValueError, match="budget"):
        extract_image(work, config, tmp_path/"state")


def test_refusal_is_recorded_and_not_exported_as_observations(tmp_path: Path) -> None:
    client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={"status":"completed","output":[{"type":"message","content":[{"type":"refusal","refusal":"No"}]}]})))
    with pytest.raises(ValueError, match="structured"):
        extract_image(job(tmp_path), settings(), tmp_path/"state", client=client)
    assert '"status": "error"' in (tmp_path/"state"/"telemetry.jsonl").read_text()


def test_prompt_targets_assigned_frontage_class(tmp_path: Path) -> None:
    def transport(request: httpx.Request) -> httpx.Response:
        prompt = json.loads(request.content)['input'][0]['content'][0]['text']
        assert 'Requested frontage class: housing' in prompt
        assert 'empty frontages list' in prompt
        return response(request)
    extract_image(job(tmp_path), settings(), tmp_path/'state',
                  client=httpx.Client(transport=httpx.MockTransport(transport)))
