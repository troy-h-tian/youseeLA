"""Reproducible local scaling measurements; no paid requests are made here."""

import argparse
import hashlib
import json
import platform
import statistics
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from youseela.contracts import Bundle
from youseela.export import build_bundle
from youseela.fixtures import make_fixture
from youseela.scoring import load_config


def summarize_telemetry(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"status":"unmeasured","reason":"No real pilot API telemetry available; no calls made for benchmark."}
    events=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    completed=[e for e in events if e.get("status")=="completed"]
    hits=[e for e in events if e.get("status")=="cache_hit"]
    if not completed:
        return {"status":"unmeasured","reason":"No completed real image requests in telemetry", "cache_hits":len(hits)}
    timings=[e["duration_seconds"] for e in completed]
    costs=[e.get("billed_cost_usd") for e in completed]
    mean_cost=statistics.mean(costs) if all(isinstance(c,(int,float)) for c in costs) else None
    return {"status":"measured_pilot","completed_requests":len(completed),"cache_hits":len(hits),
            "errors":sum(e.get("status")=="error" for e in events),
            "duration_median_seconds":statistics.median(timings),"duration_max_seconds":max(timings),
            "models":sorted({e["model"] for e in completed}),
            "mean_billed_cost_usd":mean_cost,
            "cost_note":"Reservations are not billed costs. Missing billing data is unmeasured.",
            "projected_cost_usd_six_images_per_area":{str(n):n*6*mean_cost if mean_cost is not None else None for n in [10,100,1000]},
            "projection_assumptions":"Six images per area, same provider/model/image mix and pricing; no retries. Historical corroboration may add images."}


def benchmark(sizes: list[int], runs: int = 10, telemetry: Path | None = None) -> dict[str, Any]:
    if not 1 <= runs <= 100:
        raise ValueError("Runs must be between 1 and 100")
    config=load_config()
    results=[]
    for size in sizes:
        dataset=make_fixture(size)
        build_bundle(dataset,config,date.today())  # Untimed warm-up.
        scoring=[]
        exporting=[]
        payload=""
        for _ in range(runs):
            started=time.perf_counter()
            bundle=build_bundle(dataset,config,date.today())
            scoring.append(time.perf_counter()-started)
            started=time.perf_counter()
            payload=bundle.model_dump_json()
            checked=Bundle.model_validate_json(payload)
            exporting.append(time.perf_counter()-started)
            if len(checked.areas)!=size:
                raise ValueError("Benchmark failed to consume expected records")
        results.append({"areas":size,"mode_assessments":size*2,"businesses":len(dataset.businesses),
                        "evidence_records":len(dataset.evidence),"runs":runs,
                        "score_median_seconds":statistics.median(scoring),"score_max_seconds":max(scoring),
                        "export_validate_median_seconds":statistics.median(exporting),"export_validate_max_seconds":max(exporting),
                        "areas_per_second":size/statistics.median(scoring),"output_bytes":len(payload.encode()),
                        "output_sha256":hashlib.sha256(payload.encode()).hexdigest(),"errors":0})
    return {"generated_at":datetime.now(timezone.utc).isoformat(),"data_kind":"synthetic_performance_fixture",
            "environment":{"python":platform.python_version(),"platform":platform.platform(),"processor":platform.machine()},
            "configuration":config.model_dump(),"measurements":results,"image_api":summarize_telemetry(telemetry),
            "frontend":{"status":"unmeasured","owner":"Person B"},
            "limitations":["Synthetic schema/throughput evaluation, not model accuracy or real imagery coverage.",
                           "Scoring includes geometry checks and bundle construction; export includes JSON validation.",
                           "No network, image downloads, paid calls or human review time are included in synthetic timings.",
                           "Fixture creation and one warm-up per size are excluded; timings are local to the recorded machine."]}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes",default="10,100,1000")
    parser.add_argument("--runs",type=int,default=10)
    parser.add_argument("--output",type=Path,default=Path("artifacts/scalability.json"))
    parser.add_argument("--telemetry",type=Path)
    args=parser.parse_args()
    result=benchmark([int(n) for n in args.sizes.split(",")],args.runs,args.telemetry)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n")
    for row in result["measurements"]:
        print(f"{row['areas']} synthetic areas: scoring median {row['score_median_seconds']:.4f}s; export/validate {row['export_validate_median_seconds']:.4f}s; {row['output_bytes']} bytes")
    print(f"Saved {args.output}; API and frontend measurements remain separate.")


if __name__=="__main__":
    main()
