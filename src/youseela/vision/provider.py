"""Budget-gated image extraction with redacted telemetry and explicit review."""

import base64
import fcntl
import hashlib
import json
import os
import struct
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field

from youseela.contracts import Evidence, FrontageObservation, Record
from youseela.vision.prompts import PROMPT


class VisionSettings(Record):
    provider: Literal["openai"]
    model: str = Field(min_length=1)
    api_key: str = Field(min_length=1, repr=False, exclude=True)
    budget_usd: float = Field(ge=0)
    max_cost_per_request_usd: float = Field(ge=0)

    @classmethod
    def from_env(cls) -> "VisionSettings":
        return cls(provider=os.environ.get("VISION_PROVIDER", ""), model=os.environ.get("VISION_MODEL", ""),
                   api_key=os.environ.get("VISION_API_KEY", ""), budget_usd=float(os.environ.get("VISION_BUDGET_USD", "0")),
                   max_cost_per_request_usd=float(os.environ.get("VISION_MAX_COST_PER_REQUEST_USD", "0")))


class ImageJob(Record):
    image_path: Path
    analysis_permitted: bool
    cache_permitted: bool
    evidence: Evidence


class Finding(Record):
    label: str
    visible_work: Literal["present", "absent", "unclear"]
    description: str


class Findings(Record):
    frontages: list[Finding]


def log_event(state: Path, event: dict) -> None:
    state.mkdir(parents=True, exist_ok=True)
    with (state/"telemetry.jsonl").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps({"at":datetime.now(timezone.utc).isoformat(), **event}, allow_nan=False)+"\n")


def reserve_budget(state: Path, settings: VisionSettings) -> None:
    if settings.budget_usd <= 0 or settings.max_cost_per_request_usd <= 0:
        raise ValueError("A positive approved budget and conservative per-request cost reservation are required")
    state.mkdir(parents=True, exist_ok=True)
    with (state/"budget.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = state/"budget.json"
        current = json.loads(ledger.read_text()) if ledger.exists() else {"reserved_usd":0.0,"requests":0}
        reserved = float(current["reserved_usd"]) + settings.max_cost_per_request_usd
        if reserved > settings.budget_usd + 1e-10:
            raise ValueError("Image API budget reservation limit reached; no request was sent")
        current.update(reserved_usd=reserved, requests=int(current["requests"])+1)
        temporary = ledger.with_suffix(".tmp")
        temporary.write_text(json.dumps(current))
        temporary.replace(ledger)


def extract_image(job: ImageJob, settings: VisionSettings, state: Path,
                  client: httpx.Client | None = None) -> Evidence:
    if not job.analysis_permitted:
        raise ValueError("Explicit image analysis permission is required")
    if job.evidence.kind != "image" or job.evidence.mode == "both":
        raise ValueError("A vision job needs image evidence assigned to one mode")
    if job.image_path.stat().st_size > 5_000_000:
        raise ValueError("Limit each image to 5 MB before inference")
    data = job.image_path.read_bytes()
    mime = "image/png" if data.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg" if data.startswith(b"\xff\xd8") else None
    if mime is None:
        raise ValueError("Only PNG and JPEG image files are accepted")
    width, height = struct.unpack(">II", data[16:24]) if mime == "image/png" and len(data) >= 24 else (None, None)
    signature = json.dumps({"model":settings.model,"prompt":PROMPT,"evidence":job.evidence.model_dump(mode="json")},sort_keys=True).encode()+data
    cache_key = hashlib.sha256(signature).hexdigest()
    cache = state/"cache"/f"{cache_key}.json"
    event = {"request_id":str(uuid.uuid4()),"provider":settings.provider,"model":settings.model,
             "image_id":job.evidence.id,"image_count":1,"image_bytes":len(data),
             "image_width":width,"image_height":height,"reserved_cost_usd":0.0,
             "billed_cost_usd":None,"usage":None,"retry_attempt":0}
    start = time.perf_counter()
    if job.cache_permitted and cache.exists():
        result = Evidence.model_validate_json(cache.read_text())
        log_event(state,{**event,"status":"cache_hit","duration_seconds":time.perf_counter()-start})
        return result
    reserve_budget(state, settings)
    event["reserved_cost_usd"] = settings.max_cost_per_request_usd
    log_event(state,{**event,"status":"started"})
    owned = client is None
    client = client or httpx.Client(timeout=60)
    try:
        payload = {"model":settings.model,"store":False,"max_output_tokens":1500,
                   "input":[{"role":"user","content":[{"type":"input_text","text":PROMPT},
                              {"type":"input_image","image_url":f"data:{mime};base64,"+base64.b64encode(data).decode(),"detail":"low"}]}],
                   "text":{"format":{"type":"json_schema","name":"visible_frontages","strict":True,"schema":Findings.model_json_schema()}}}
        response = client.post("https://api.openai.com/v1/responses", headers={"Authorization":f"Bearer {settings.api_key}"},json=payload)
        if response.status_code != 200:
            raise ValueError(f"Vision provider returned HTTP {response.status_code}; no automatic paid retry")
        body = response.json()
        event["usage"] = body.get("usage")
        text = "".join(part.get("text", "") for output in body.get("output", []) if output.get("type") == "message"
                       for part in output.get("content", []) if part.get("type") == "output_text")
        if body.get("status") != "completed" or not text:
            raise ValueError("Vision response did not contain completed structured observations")
        findings = Findings.model_validate_json(text)
        draft = job.evidence.model_copy(deep=True)
        draft.reviewed = False
        # These IDs must be aligned by a person when multiple photos show one frontage.
        draft.observations = [FrontageObservation(frontage_id=f"{draft.site_id}-candidate-{i}",
                                                  redevelopment=f.visible_work, corroboration_ids=[],
                                                  description=f"{f.label}: {f.description}") for i,f in enumerate(findings.frontages)]
        draft.note = "Unreviewed vision extraction. Visible work is not confirmed redevelopment. Verify findings, align frontage IDs, and add independent corroboration before export."
        if job.cache_permitted:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(draft.model_dump_json(indent=2)+"\n")
        log_event(state,{**event,"status":"completed","duration_seconds":time.perf_counter()-start})
        return draft
    except Exception as error:
        log_event(state,{**event,"status":"error","error_type":type(error).__name__,"duration_seconds":time.perf_counter()-start})
        if isinstance(error, httpx.HTTPError):
            raise ValueError("Vision request failed; reservation retained because billing status is unknown") from None
        raise
    finally:
        if owned:
            client.close()
