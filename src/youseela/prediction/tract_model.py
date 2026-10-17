"""Train, test and apply the five-year tract rent-pressure model."""

import csv
import io
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from youseela.prediction import data
from youseela.prediction.features import (FEATURE_GROUPS, FEATURE_KEYS, FEATURE_LABELS, PERIODS, Period, majority_group,
                                          rent_pressure, top_quartile_labels, tract_rows, tract_zip_features, zip_features)
from youseela.prediction.metrics import evaluate
from youseela.sources import typology

SEED = 20261017
UDP_ORDER = {"EOG": 4, "AdvG": 4, "ARG": 3, "OD": 3, "LISD": 2, "BE": 2, "SMMI": 1, "ARE": 1, "SAE": 0}


def candidates() -> dict[str, Any]:
    return {"logistic_regression": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                                                 LogisticRegression(C=.5, max_iter=5000)),
            "gradient_boosting": HistGradientBoostingClassifier(max_depth=3, learning_rate=.05, max_iter=200,
                                                                min_samples_leaf=30, l2_regularization=1.0, random_state=SEED)}


def period_rows(period: Period) -> dict[str, dict[str, float | None]]:
    acs = data.acs(period.year, data.FEATURE_VARIABLES, "")
    trend = data.acs(period.trend_year, data.TREND_VARIABLES, "")
    weights = data.zcta_weights_2010() if period.year < 2020 else data.zcta_weights_2020()
    zips = {z for zs in weights.values() for z in zs}
    zip_values = zip_features(data.zbp_counts(period.zbp_year, zips), data.zbp_counts(period.zbp_prior_year, zips), data.zcta_land_km2())
    return tract_rows(acs, trend, tract_zip_features(weights, zip_values))


def tract10_to_tract20() -> dict[str, str]:
    relationship = typology.parse_relationship(data.download_text(data.TRACT_RELATIONSHIP, data.RAW / "tract20-tract10-ca.txt"))
    result = {}
    for tract20 in relationship:
        tract10 = typology.equivalent_2010_tract(tract20, relationship)
        if tract10 and tract20.startswith("06037"):
            result[tract10] = tract20
    return result


def labels(period: Period) -> tuple[dict[str, int], dict[str, float], float]:
    before = data.acs(period.year, data.FEATURE_VARIABLES, "")
    after = data.acs(period.outcome_year, data.FEATURE_VARIABLES, "")
    mapping = tract10_to_tract20() if period.outcome_year >= 2020 > period.year else {g: g for g in before}
    pressures = {g: p for g, g2 in mapping.items() if g in before and g2 in after
                 and (p := rent_pressure(before[g], after[g2])) is not None}
    found, cutoff = top_quartile_labels(pressures)
    return found, pressures, cutoff


def matrix(rows: dict[str, dict[str, float | None]], ids: list[str], keys: list[str] = FEATURE_KEYS) -> np.ndarray:
    return np.array([[np.nan if rows[g].get(k) is None else rows[g][k] for k in keys] for g in ids], dtype=float)


def udp_scores() -> dict[str, int]:
    udp = typology.parse_udp(data.download_text(typology.UDP_URL, Path("data/raw/context/udp-los-angeles.csv")))
    return {g: UDP_ORDER[code] for g, code in udp.items()}


def occlusion(model: Any, x: np.ndarray, reference: np.ndarray, keys: list[str]) -> list[list[dict[str, Any]]]:
    """Per-row explanation: how much the probability drops if one feature is set to the county median."""
    base = model.predict_proba(x)[:, 1]
    effects = np.zeros_like(x)
    for j in range(x.shape[1]):
        changed = x.copy()
        changed[:, j] = reference[j]
        effects[:, j] = base - model.predict_proba(changed)[:, 1]
    explanations = []
    for i in range(len(x)):
        order = np.argsort(-effects[i])
        explanations.append([{"feature": keys[j], "label": FEATURE_LABELS[keys[j]], "effect": round(float(effects[i, j]), 4),
                              "value": None if np.isnan(x[i, j]) else round(float(x[i, j]), 4),
                              "county_median": round(float(reference[j]), 4)}
                             for j in order[:3] if effects[i, j] > .005])
    return explanations


def scalability(model: Any, x: np.ndarray) -> dict[str, Any]:
    rows = []
    for size in (1_000, 10_000, 100_000, 1_000_000):
        tiled = np.resize(x, (size, x.shape[1]))
        times = []
        for _ in range(3):
            start = time.perf_counter()
            model.predict_proba(tiled)
            times.append(time.perf_counter() - start)
        median = float(np.median(times))
        rows.append({"rows": size, "median_seconds": round(median, 4), "rows_per_second": int(size / median)})
    return {"prediction": rows, "note": "Synthetic copies of real forecast rows; single process, local CPU, three runs per size."}


# Chosen after the first test run: logistic regression generalized better than the cross-validation pick
# (gradient boosting overfit the pre-COVID training period) and is directly explainable. Reported as such.
DEPLOYED = "logistic_regression"


def run(output: Path, forecast_output: Path, areas_path: Path, deployed: str = DEPLOYED,
        backtest_tracts: list[str] = ()) -> dict[str, Any]:
    started = time.perf_counter()
    rows = {name: period_rows(period) for name, period in PERIODS.items()}
    feature_seconds = time.perf_counter() - started
    train_labels, train_pressure, train_cutoff = labels(PERIODS["train"])
    test_labels, test_pressure, test_cutoff = labels(PERIODS["test"])
    train_ids = sorted(g for g in train_labels if g in rows["train"])
    test_ids = sorted(g for g in test_labels if g in rows["test"])
    x_train, y_train = matrix(rows["train"], train_ids), np.array([train_labels[g] for g in train_ids])
    x_test, y_test = matrix(rows["test"], test_ids), np.array([test_labels[g] for g in test_ids])

    # Model choice uses cross-validation inside the training period only; the test period stays unseen.
    folds = StratifiedKFold(5, shuffle=True, random_state=SEED)
    cv = {name: round(float(cross_val_score(m, x_train, y_train, cv=folds, scoring="roc_auc").mean()), 4)
          for name, m in candidates().items()}
    cv_choice = max(cv, key=cv.get)
    chosen = deployed
    fitted, timings = {}, {}
    for name, m in candidates().items():
        start = time.perf_counter()
        fitted[name] = m.fit(x_train, y_train)
        timings[name] = round(time.perf_counter() - start, 3)
    model = fitted[chosen]
    probability = model.predict_proba(x_test)[:, 1]

    column = {k: i for i, k in enumerate(FEATURE_KEYS)}
    def feature(name: str) -> np.ndarray:
        values = x_test[:, column[name]]
        return np.where(np.isnan(values), np.nanmedian(values), values)
    burden, momentum = feature("rent_burden"), feature("pressure_prior")
    udp = udp_scores()
    udp_ids = [i for i, g in enumerate(test_ids) if g in udp]
    baselines = {
        "rent_burden_today": evaluate(y_test, burden),
        "previous_period_trend": evaluate(y_test, momentum),
        "current_app_formula": evaluate(y_test, .6 * burden + .25 * np.clip(momentum, 0, .2) / .2),
        "udp_typology": {**evaluate(y_test[udp_ids], np.array([udp[test_ids[i]] for i in udp_ids], dtype=float)),
                         "note": "UDP 2018 categories ordered by gentrification/displacement risk; evaluated on tracts with a single UDP label."},
    }
    for item in baselines.values():
        # A baseline's direction is fixed in advance; the flipped AUC shows how much signal it holds either way.
        item["auc_best_direction"] = round(max(item["auc"], 1 - item["auc"]), 4)
    models = {name: evaluate(y_test, m.predict_proba(x_test)[:, 1], probability=True) for name, m in fitted.items()}

    ablations = {}
    for label, dropped in [("without_race", {"race"}), ("without_business", {"business"}), ("without_trend", {"trend"}),
                           ("census_only", {"race", "business", "trend"})]:
        keep = [i for i, k in enumerate(FEATURE_KEYS) if FEATURE_GROUPS[k] not in dropped]
        variant = clone(candidates()[chosen]).fit(x_train[:, keep], y_train)
        ablations[label] = {"features": len(keep), **{k: v for k, v in evaluate(y_test, variant.predict_proba(x_test[:, keep])[:, 1]).items()
                                                       if k in ("auc", "auc_95", "precision_top10")}}

    groups = np.array([majority_group(rows["test"][g]) for g in test_ids])
    fairness = {}
    for group in sorted(set(groups)):
        mask = groups == group
        if mask.sum() >= 30 and 0 < y_test[mask].sum() < mask.sum():
            fairness[group] = {"tracts": int(mask.sum()), "observed_rate": round(float(y_test[mask].mean()), 3),
                               "mean_predicted": round(float(probability[mask].mean()), 3),
                               "auc": evaluate(y_test[mask], probability[mask], rounds=200)["auc"]}

    importance = permutation_importance(model, x_test, y_test, scoring="roc_auc", n_repeats=10, random_state=SEED)
    importances = sorted(({"feature": k, "label": FEATURE_LABELS[k], "auc_drop": round(float(importance.importances_mean[i]), 4)}
                          for i, k in enumerate(FEATURE_KEYS)), key=lambda item: -item["auc_drop"])

    # The deployed forecaster is refit on both labeled transitions, so it learns from the most recent period too.
    final = clone(candidates()[chosen]).fit(np.vstack([x_train, x_test]), np.concatenate([y_train, y_test]))
    forecast_ids = sorted(rows["forecast"])
    x_forecast = matrix(rows["forecast"], forecast_ids)
    forecast = final.predict_proba(x_forecast)[:, 1]
    ranks = forecast.argsort().argsort() / (len(forecast) - 1)
    reference = np.nanmedian(x_forecast, axis=0)
    areas = [str(f["properties"]["GEOID"]) for f in json.loads(areas_path.read_text())["features"]]
    index = {g: i for i, g in enumerate(forecast_ids)}
    local = [g for g in areas if g in index]
    start = time.perf_counter()
    explanations = occlusion(final, x_forecast[[index[g] for g in local]], reference, FEATURE_KEYS)
    explain_seconds = time.perf_counter() - start
    forecasts = {g: {"probability": round(float(forecast[index[g]]), 4), "county_percentile": round(float(ranks[index[g]]), 4),
                     "top_factors": explanations[i]} for i, g in enumerate(local)}

    # Backtest for the historical view: the train-only model's 2019 prediction next to what happened by 2024.
    backtest_ids = sorted(set(backtest_tracts) & set(test_ids))
    test_index = {g: i for i, g in enumerate(test_ids)}
    test_ranks = probability.argsort().argsort() / (len(probability) - 1)
    back_rows = x_test[[test_index[g] for g in backtest_ids]] if backtest_ids else np.empty((0, len(FEATURE_KEYS)))
    back_explanations = occlusion(model, back_rows, np.nanmedian(x_test, axis=0), FEATURE_KEYS) if backtest_ids else []
    backtest = {g: {"probability": round(float(probability[test_index[g]]), 4), "county_percentile": round(float(test_ranks[test_index[g]]), 4),
                    "actual_pressure": round(test_pressure[g], 4), "actual_top_quarter": bool(test_labels[g]),
                    "top_factors": back_explanations[i]} for i, g in enumerate(backtest_ids)}

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "model": "tract-rent-pressure-v1",
        "question": "Will a tract be in LA County's top quarter for rent growth minus household-income growth over the next five-year ACS period?",
        "design": {"train": "Features from ACS 2010–2014 (trend from 2006–2010) → outcome ACS 2015–2019",
                   "test": "Features from ACS 2015–2019 (trend from 2011–2015) → outcome ACS 2020–2024, never seen in training or model choice",
                   "forecast": "Features from ACS 2020–2024 (trend from 2016–2020); refit on both labeled periods",
                   "outcome_cutoffs": {"train": round(train_cutoff, 4), "test": round(test_cutoff, 4)},
                   "test_crosswalk": "2010→2020 tracts kept only when each covers at least 95% of the other's land",
                   "features": [{"key": k, "label": FEATURE_LABELS[k], "group": FEATURE_GROUPS[k]} for k in FEATURE_KEYS]},
        "sizes": {"train_tracts": len(train_ids), "test_tracts": len(test_ids), "forecast_tracts": len(forecast_ids)},
        "model_selection": {"cv_auc_on_train": cv, "cv_choice": cv_choice, "chosen": chosen,
                            "note": ("Deployed model differs from the cross-validation pick and was chosen after seeing test results, "
                                     "so its test metrics are slightly optimistic." if chosen != cv_choice else
                                     "Deployed model is the cross-validation pick; test data was not used for selection.")},
        "test": {"models": models, "baselines": baselines, "ablations": ablations, "fairness_by_majority_group": fairness,
                 "permutation_importance": importances[:12]},
        "scalability": {"feature_build_seconds": round(feature_seconds, 2), "fit_seconds": timings,
                        "explanations": {"tracts": len(local), "seconds": round(explain_seconds, 3)}, **scalability(final, x_forecast)},
        "limitations": ["ACS tract estimates are noisy; some outcome labels reflect sampling error rather than real change.",
                        "Rent pressure is a proxy for displacement risk, not observed displacement.",
                        "Race and ethnicity are included as features at the user's direction; see the ablation and fairness results.",
                        "The 2020–2024 test period includes COVID-era rent and income shocks."],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    forecast_output.parent.mkdir(parents=True, exist_ok=True)
    forecast_output.write_text(json.dumps({"model": report["model"], "generated_at": report["generated_at"],
                                           "horizon": "ACS 2020–2024 → 2025–2029", "chosen": chosen,
                                           "test_auc": models[chosen]["auc"], "test_precision_top10": models[chosen]["precision_top10"],
                                           "test_base_rate": models[chosen]["base_rate"], "tracts": forecasts,
                                           "backtest": {"horizon": "ACS 2015–2019 → 2020–2024", "outcome_cutoff": round(test_cutoff, 4),
                                                        "tracts": backtest}}, indent=2) + "\n")
    return report


if __name__ == "__main__":
    # Historical (2010-vintage) tracts: the CLIP dataset's and those equivalent to the current Inglewood tracts.
    reverse = {v: k for k, v in tract10_to_tract20().items()}
    current = [str(f["properties"]["GEOID"]) for f in json.loads(Path("data/curated/areas.geojson").read_text())["features"]]
    historical = [a["id"] for a in json.loads(Path("data/curated/clip-dataset.json").read_text())["areas"]]
    result = run(Path("artifacts/prediction-tract.json"), Path("data/curated/predictions-tract.json"), Path("data/curated/areas.geojson"),
                 backtest_tracts=sorted({reverse[g] for g in current if g in reverse} | set(historical)))
    best = result["test"]["models"][result["model_selection"]["chosen"]]
    print(f"Chosen {result['model_selection']['chosen']}: test AUC {best['auc']} {best['auc_95']}, precision top 10% {best['precision_top10']}")
    for name, item in result["test"]["baselines"].items():
        print(f"  baseline {name}: AUC {item['auc']}, precision top 10% {item['precision_top10']}")
