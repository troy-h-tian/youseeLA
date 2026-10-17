"""Small human-labeled image evaluation, separate from area-model validity."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from youseela.contracts import Evidence
from youseela.vision.prompts import PROMPT, prompt_for_mode

LABELS = ('present', 'absent', 'unclear', 'unusable')


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def image_prediction(evidence: Evidence) -> str:
    statuses = {item.redevelopment for item in evidence.observations}
    if not statuses:
        return 'unusable'
    if 'present' in statuses:
        return 'present'
    if 'unclear' in statuses:
        return 'unclear'
    return 'absent'


def evaluate_labels(reference: dict[str, str], predictions: dict[str, str]) -> dict[str, Any]:
    if not reference or set(reference) != set(predictions):
        raise ValueError('Reference and prediction files need the same image IDs and a nonempty sample')
    if any(value not in LABELS for value in [*reference.values(), *predictions.values()]):
        raise ValueError('Labels must be present, absent, unclear, or unusable; pending labels cannot be evaluated')
    matrix = {actual: {predicted: 0 for predicted in LABELS} for actual in LABELS}
    for key, actual in reference.items():
        matrix[actual][predictions[key]] += 1
    per_class = {}
    for label in LABELS:
        tp = matrix[label][label]
        actual_count = sum(matrix[label].values())
        predicted_count = sum(matrix[actual][label] for actual in LABELS)
        per_class[label] = dict(reference_count=actual_count, predicted_count=predicted_count,
                                precision=ratio(tp, predicted_count), recall=ratio(tp, actual_count),
                                f1=ratio(2 * tp, actual_count + predicted_count))
    clear = [key for key, label in reference.items() if label in {'present', 'absent'}]
    decisive = [key for key in clear if predictions[key] in {'present', 'absent'}]
    correct = sum(reference[key] == predictions[key] for key in reference)
    return dict(sample_size=len(reference), human_label_agreement=correct / len(reference),
                confusion_matrix_rows_reference=matrix, per_class=per_class,
                clear_reference_count=len(clear),
                decisive_coverage_on_clear_references=ratio(len(decisive), len(clear)),
                selective_accuracy_on_clear_references=ratio(sum(reference[key] == predictions[key] for key in decisive), len(decisive)),
                gentrification_prediction_accuracy=None,
                always_absent_baseline_agreement=sum(value == "absent" for value in reference.values()) / len(reference),
                construction_positive_reference_count=sum(value == "present" for value in reference.values()),
                limitations=['Single-reviewer pilot labels, not independently adjudicated ground truth.',
                             'Small spatially clustered historical sample; not representative of all neighborhoods.',
                             'Undefined metrics remain null when a class or prediction denominator is absent.',
                             'Visible physical work is not displacement, financial distress, or corroborated redevelopment.',
                             'Selective accuracy excludes abstentions; read it together with coverage.',
                             'This evaluates image observations, not area score accuracy.'])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/image-evaluation.json'))
    args = parser.parse_args()
    labels = json.loads(args.labels.read_text())
    rows = labels['decisions']
    evidence = [Evidence.model_validate(row) for row in json.loads(args.predictions.read_text())]
    if len({row['image_id'] for row in rows}) != len(rows) or len({item.id for item in evidence}) != len(evidence):
        raise ValueError('Duplicate image IDs in evaluation input')
    reference = {row['image_id']: row['label'] for row in rows}
    predictions = {item.id: image_prediction(item) for item in evidence}
    report = evaluate_labels(reference, predictions)
    report.update(generated_at=datetime.now(timezone.utc).isoformat(), protocol=labels.get('protocol'),
                  labels_sha256=hashlib.sha256(args.labels.read_bytes()).hexdigest(),
                  predictions_sha256=hashlib.sha256(args.predictions.read_bytes()).hexdigest(),
                  current_prompt_sha256=hashlib.sha256(PROMPT.encode()).hexdigest(),
                  mode_prompt_sha256={mode: hashlib.sha256(prompt_for_mode(mode).encode()).hexdigest() for mode in ("housing", "commercial")},
                  cases=[dict(image_id=key, reference=reference[key], prediction=predictions[key]) for key in sorted(reference)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(f"Image-label agreement: {report['human_label_agreement']:.1%} on {report['sample_size']} images; not area-risk accuracy. Saved {args.output}")


if __name__ == '__main__':
    main()
