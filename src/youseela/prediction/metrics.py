"""Evaluation metrics with bootstrap intervals, computed the same way for models and baselines."""

from typing import Any

import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def precision_at(y: np.ndarray, score: np.ndarray, share: float = .1) -> float:
    """Of the top `share` of cases ranked by score, the fraction that are positive."""
    k = max(1, int(round(share * len(y))))
    return float(y[np.argsort(-score, kind="stable")[:k]].mean())


def lift_at(y: np.ndarray, score: np.ndarray, share: float = .1) -> float:
    return precision_at(y, score, share) / float(y.mean())


def bootstrap(y: np.ndarray, score: np.ndarray, rounds: int = 500, seed: int = 0) -> dict[str, list[float]]:
    rng = np.random.default_rng(seed)
    aucs, precisions = [], []
    for _ in range(rounds):
        index = rng.integers(0, len(y), len(y))
        if y[index].min() == y[index].max():
            continue
        aucs.append(roc_auc_score(y[index], score[index]))
        precisions.append(precision_at(y[index], score[index]))
    interval = lambda values: [round(float(np.percentile(values, 2.5)), 3), round(float(np.percentile(values, 97.5)), 3)]
    return {"auc_95": interval(aucs), "precision_top10_95": interval(precisions)}


def calibration(y: np.ndarray, probability: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    """Mean predicted probability versus observed rate in equal-size bins."""
    order = np.argsort(probability, kind="stable")
    return [{"predicted": round(float(probability[part].mean()), 4), "observed": round(float(y[part].mean()), 4), "n": int(len(part))}
            for part in np.array_split(order, bins) if len(part)]


def evaluate(y: np.ndarray, score: np.ndarray, probability: bool = False, rounds: int = 500) -> dict[str, Any]:
    """Ranking metrics for any score; probability metrics only when the score is a calibrated-style probability."""
    result: dict[str, Any] = {"n": int(len(y)), "positives": int(y.sum()), "base_rate": round(float(y.mean()), 4),
                              "auc": round(float(roc_auc_score(y, score)), 4),
                              "average_precision": round(float(average_precision_score(y, score)), 4),
                              "precision_top10": round(precision_at(y, score), 4),
                              "lift_top10": round(lift_at(y, score), 3),
                              **bootstrap(y, score, rounds)}
    if probability:
        result["brier"] = round(float(brier_score_loss(y, score)), 4)
        result["brier_base_rate"] = round(float(brier_score_loss(y, np.full(len(y), y.mean()))), 4)
        result["calibration"] = calibration(y, score)
    return result
