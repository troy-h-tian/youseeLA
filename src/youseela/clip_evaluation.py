"""Measure CLIP fusion sensitivity and scaling; neither is predictive accuracy."""
import argparse
import json
import platform
import statistics
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from youseela.contracts import Bundle, Dataset
from youseela.export import build_bundle
from youseela.scoring import AssessmentConfig, load_config


def replicated_fixture(dataset: Dataset, count: int) -> Dataset:
    """Repeat a source-backed template as explicitly synthetic workload records."""
    template = next(a for a in dataset.areas if a.indicators.affordability_pressure is not None)
    records = [e for e in dataset.evidence if e.area_id == template.id]
    pairs = [p for p in dataset.clip_pairs if p.area_id == template.id]
    areas, evidence, features = [], [], []
    for index in range(count):
        prefix = f'synthetic-{index}-'
        area = template.model_copy(deep=True)
        area.id = prefix + template.id
        area.name = f'Synthetic workload area {index}'
        area.indicators.evidence_ids = [prefix + ref for ref in area.indicators.evidence_ids]
        areas.append(area)
        for original in records:
            item = original.model_copy(deep=True)
            item.id, item.area_id, item.data_kind = prefix + item.id, area.id, 'fixture'
            item.site_id = prefix + item.site_id if item.site_id else None
            evidence.append(item)
        for original in pairs:
            pair = original.model_copy(deep=True)
            pair.id, pair.area_id, pair.site_id = prefix + pair.id, area.id, prefix + pair.site_id
            pair.earlier_image_id = prefix + pair.earlier_image_id
            pair.later_image_id = prefix + pair.later_image_id
            features.append(pair)
    return Dataset(data_kind='fixture', areas=areas, evidence=evidence, clip_pairs=features)


def evaluate(dataset: Dataset, config: AssessmentConfig, sizes: list[int], runs: int) -> dict[str, Any]:
    if runs < 3 or any(n < 1 for n in sizes):
        raise ValueError('Use at least three repetitions and positive area counts')
    as_of = date(2020, 12, 31)
    real = build_bundle(dataset, config, as_of)
    ablations = []
    for area in real.areas:
        for mode in ('housing', 'commercial'):
            assessment = getattr(area, mode)
            if assessment.score is None:
                continue
            visual = next(c for c in assessment.contributions if c.feature == 'clip_visual_difference')
            numerical = sum(c.points for c in assessment.contributions if c.feature != visual.feature)
            zero = dataset.model_copy(deep=True)
            for pair in zero.clip_pairs:
                pair.cosine_similarity, pair.visual_difference = 1.0, 0.0
            zero_bundle = build_bundle(zero, config, as_of)
            zero_score = getattr(next(a for a in zero_bundle.areas if a.id == area.id), mode).score
            assert zero_score is not None and abs(assessment.score-zero_score-visual.points) < 1e-5
            weights = [0, .1, .2, .3]
            sensitivity = [{'visual_weight': w, 'score': numerical/(1-visual.weight)*(1-w)+100*w*visual.value} for w in weights]
            ablations.append(dict(area_id=area.id, mode=mode, combined_score=assessment.score,
                                  zero_visual_score=zero_score, visual_points=visual.points,
                                  numerical_only_renormalized=numerical/(1-visual.weight),
                                  weight_sensitivity=sensitivity, ablation_passed=True))
    measurements = []
    for size in sizes:
        fixture = replicated_fixture(dataset, size)
        build_bundle(fixture, config, as_of)
        scoring, exporting = [], []
        payload = ''
        for _ in range(runs):
            start = time.perf_counter()
            bundle = build_bundle(fixture, config, as_of)
            scoring.append(time.perf_counter()-start)
            start = time.perf_counter()
            payload = bundle.model_dump_json()
            checked = Bundle.model_validate_json(payload)
            exporting.append(time.perf_counter()-start)
            assert len(checked.areas) == size and sum(a.commercial.status == 'rated' for a in checked.areas) == size
        measurements.append(dict(areas=size, image_pairs=len(fixture.clip_pairs), runs=runs, errors=0,
                                 build_median_ms=statistics.median(scoring)*1000,
                                 build_max_ms=max(scoring)*1000,
                                 export_validate_median_ms=statistics.median(exporting)*1000,
                                 export_validate_max_ms=max(exporting)*1000,
                                 output_bytes=len(payload.encode())))
    return dict(generated_at=datetime.now(timezone.utc).isoformat(),
                environment=dict(python=platform.python_version(), machine=platform.machine(), platform=platform.platform()),
                accuracy_measured=False, real_pair_count=len(dataset.clip_pairs), ablations=ablations,
                scaling=dict(data_kind='synthetic_replicated_workload', measurements=measurements,
                             limitations=['Precomputed CLIP features; no image encoding, downloading, or networking in these timings.',
                                          'Repeated geographic template is a load test, not evidence about additional real areas.',
                                          'Fixture creation and one warm-up excluded. Single local process, not a production capacity guarantee.']))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path('data/curated/clip-dataset.json'))
    parser.add_argument('--config', type=Path, default=Path('config/clip-assessment.json'))
    parser.add_argument('--sizes', default='10,100,1000')
    parser.add_argument('--runs', type=int, default=10)
    parser.add_argument('--output', type=Path, default=Path('artifacts/clip-evaluation.json'))
    args = parser.parse_args()
    result = evaluate(Dataset.model_validate_json(args.input.read_text()), load_config(args.config),
                      [int(n) for n in args.sizes.split(',')], args.runs)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
