"""Train and test a five-year closure model for consumer-facing businesses, then apply it by area and type."""

import json
import re
import time
from datetime import date, datetime, timezone
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
from youseela.prediction.features import (FEATURE_GROUPS, FEATURE_KEYS, FEATURE_LABELS, PERIODS, majority_group,
                                          tract_rows, zip_features)
from youseela.prediction.metrics import evaluate
from youseela.prediction.tract_model import SEED, matrix

# ZIP-level ACS starts in 2011, so the training trend spans three years instead of four.
ZIP_TREND_YEARS = {"train": 2011, "test": 2015, "forecast": 2020}

# Business type from name keywords. NAICS cannot be used: the City strips it from closed accounts, so it would
# leak the outcome. Names are kept for open and closed businesses alike.
KEYWORDS = {
    "Food & drink": {"RESTAURANT", "CAFE", "COFFEE", "TACO", "TACOS", "TAQUERIA", "PIZZA", "PIZZERIA", "BURGER", "BURGERS",
                     "KITCHEN", "GRILL", "BAKERY", "DONUT", "DONUTS", "SUSHI", "BBQ", "DELI", "FOOD", "FOODS", "DINER", "BISTRO",
                     "EATERY", "CANTINA", "BOBA", "TEA", "JUICE", "WINGS", "PHO", "RAMEN", "BAR", "BREWING", "BREWERY", "CREAMERY",
                     "CATERING", "CHICKEN", "NOODLE", "NOODLES", "THAI", "BAKE", "DESSERTS", "ICE CREAM"},
    "Retail": {"MARKET", "STORE", "SHOP", "BOUTIQUE", "LIQUOR", "MART", "PHARMACY", "FLORIST", "FLOWERS", "JEWELRY", "JEWELERS",
               "CLOTHING", "APPAREL", "FURNITURE", "HARDWARE", "BOOKS", "SHOES", "GIFTS", "SUPERMARKET", "GROCERY", "OUTLET", "THRIFT"},
    "Personal services": {"SALON", "BARBER", "BARBERSHOP", "BEAUTY", "NAILS", "NAIL", "SPA", "LAUNDRY", "LAUNDROMAT", "CLEANERS",
                          "TAILOR", "TAILORING", "TATTOO", "FITNESS", "GYM", "YOGA", "LASH", "LASHES", "BROWS", "HAIR", "MASSAGE",
                          "CARWASH", "AUTO", "REPAIR"},
}
CATEGORY_NAMES = ["Food & drink", "Retail", "Personal services", "Other"]
CONSUMER_TYPES = CATEGORY_NAMES[:3]
COHORTS = {"train": (date(2014, 12, 31), date(2019, 12, 31)), "test": (date(2019, 12, 31), date(2024, 12, 31))}
BUSINESS_FEATURES = ["age_years", "log_age"] + [f"category_{name}" for name in CATEGORY_NAMES]
BUSINESS_LABELS = {"age_years": "Years in business at this location", "log_age": "Years in business (log)",
                   **{f"category_{n}": f"Business type: {n}" for n in CATEGORY_NAMES}}


def category(name: str) -> str:
    words = set(re.findall(r"[A-Z]+", name.upper()))
    joined = " ".join(re.findall(r"[A-Z]+", name.upper()))
    return next((kind for kind, keys in KEYWORDS.items() if words & keys or any(" " in k and k in joined for k in keys)), "Other")


def parse(day: str | None) -> date | None:
    try:
        return date.fromisoformat(day) if day else None
    except ValueError:
        return None


def cohort(businesses: list[dict[str, Any]], as_of: date, horizon: date) -> list[dict[str, Any]]:
    """Businesses open on `as_of`; label 1 if the location closed or moved by `horizon`."""
    result = []
    for item in businesses:
        start, end, kind = parse(item["start"]), parse(item["end"]), category(item["name"])
        if start is None or start > as_of or (end is not None and end <= as_of):
            continue
        result.append({**item, "category": kind, "age_years": min((as_of - start).days / 365.25, 80),
                       "closed": int(end is not None and end <= horizon)})
    return result


def zip_rows(name: str) -> dict[str, dict[str, float | None]]:
    """Area features for every LA County ZIP (ZCTA), built exactly like the tract features."""
    period = PERIODS[name]
    zips = {z for weights in (data.zcta_weights_2010(), data.zcta_weights_2020()) for zs in weights.values() for z in zs}
    acs = data.acs_zcta(period.year, data.FEATURE_VARIABLES, "", zips)
    trend = data.acs_zcta(ZIP_TREND_YEARS[name], data.TREND_VARIABLES, "", zips)
    businesses = zip_features(data.zbp_counts(period.zbp_year, zips), data.zbp_counts(period.zbp_prior_year, zips), data.zcta_land_km2())
    return tract_rows(acs, trend, businesses)


def dominant_zip(tract: str, weights: dict[str, dict[str, float]]) -> str | None:
    shares = weights.get(tract, {})
    return max(shares, key=shares.get) if shares else None


def business_matrix(rows: list[dict[str, Any]], zips: list[str], zip_values: dict[str, dict[str, float | None]]) -> np.ndarray:
    own = np.array([[r["age_years"], np.log1p(r["age_years"])] + [float(r["category"] == n) for n in CATEGORY_NAMES] for r in rows])
    return np.hstack([own, matrix(zip_values, zips)])


def candidates() -> dict[str, Any]:
    return {"logistic_regression": make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=.5, max_iter=5000)),
            "gradient_boosting": HistGradientBoostingClassifier(max_depth=4, learning_rate=.08, max_iter=250,
                                                                min_samples_leaf=200, l2_regularization=1.0, random_state=SEED)}


def run(output: Path, forecast_output: Path, areas_path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    businesses = data.la_city_businesses()
    zip_values = {name: zip_rows(name) for name in ("train", "test", "forecast")}
    sets = {}
    for name, (as_of, horizon) in COHORTS.items():
        rows = [r for r in cohort(businesses, as_of, horizon) if r["zip"] in zip_values[name]]
        zips = [r["zip"] for r in rows]
        sets[name] = (rows, zips, business_matrix(rows, zips, zip_values[name]), np.array([r["closed"] for r in rows]))
    build_seconds = time.perf_counter() - started
    keys = BUSINESS_FEATURES + FEATURE_KEYS
    labels = {**BUSINESS_LABELS, **FEATURE_LABELS}
    _, _, x_train, y_train = sets["train"]
    test_rows, test_zips, x_test, y_test = sets["test"]

    rng = np.random.default_rng(SEED)
    sample = rng.choice(len(y_train), min(60_000, len(y_train)), replace=False)
    folds = StratifiedKFold(5, shuffle=True, random_state=SEED)
    cv = {name: round(float(cross_val_score(m, x_train[sample], y_train[sample], cv=folds, scoring="roc_auc").mean()), 4)
          for name, m in candidates().items()}
    chosen = max(cv, key=cv.get)
    fitted, timings = {}, {}
    for name, m in candidates().items():
        start = time.perf_counter()
        fitted[name] = m.fit(x_train, y_train)
        timings[name] = round(time.perf_counter() - start, 3)
    model = fitted[chosen]
    probability = model.predict_proba(x_test)[:, 1]
    models = {name: evaluate(y_test, m.predict_proba(x_test)[:, 1], probability=True, rounds=200) for name, m in fitted.items()}
    consumer = np.array([r["category"] in CONSUMER_TYPES for r in test_rows])
    consumer_subset = {**evaluate(y_test[consumer], probability[consumer], rounds=200),
                       "note": "Test businesses whose names mark them as food & drink, retail or personal services."}

    # Baselines: age alone, business type alone, and each ZIP's closure rate in the previous five years.
    train_rows, train_zips = sets["train"][0], sets["train"][1]
    type_rate = {n: float(np.mean([r["closed"] for r in train_rows if r["category"] == n])) for n in CATEGORY_NAMES}
    type_counts = {name: {n: sum(1 for r in sets[name][0] if r["category"] == n) for n in CATEGORY_NAMES} for name in sets}
    prior_rate: dict[str, list[int]] = {}
    for r, z in zip(train_rows, train_zips):
        prior_rate.setdefault(z, []).append(r["closed"])
    county_rate = float(y_train.mean())
    zip_rate = np.array([np.mean(prior_rate[z]) if len(prior_rate.get(z, [])) >= 20 else county_rate for z in test_zips])
    baselines = {"younger_business_first": evaluate(y_test, -x_test[:, 0], rounds=200),
                 "business_type_rate": evaluate(y_test, np.array([type_rate[r["category"]] for r in test_rows]), rounds=200),
                 "zip_closure_rate_2015_2019": {**evaluate(y_test, zip_rate, rounds=200),
                                                   "note": "City-only signal: not available for Inglewood, so it is a baseline, not a feature."}}

    column = {k: i for i, k in enumerate(keys)}
    ablations = {}
    for label, dropped in [("without_race", {"race"}), ("without_area_features", {"census", "race", "trend", "business"})]:
        keep = [column[k] for k in keys if k in BUSINESS_FEATURES or FEATURE_GROUPS[k] not in dropped]
        variant = clone(candidates()[chosen]).fit(x_train[:, keep], y_train)
        ablations[label] = {"features": len(keep), **{k: v for k, v in evaluate(y_test, variant.predict_proba(x_test[:, keep])[:, 1], rounds=200).items()
                                                       if k in ("auc", "auc_95", "precision_top10")}}

    groups = np.array([majority_group(zip_values["test"][z]) for z in test_zips])
    fairness = {g: {"businesses": int((groups == g).sum()), "observed_rate": round(float(y_test[groups == g].mean()), 3),
                    "mean_predicted": round(float(probability[groups == g].mean()), 3),
                    "auc": evaluate(y_test[groups == g], probability[groups == g], rounds=100)["auc"]}
                for g in sorted(set(groups)) if (groups == g).sum() >= 500}

    subset = rng.choice(len(y_test), min(40_000, len(y_test)), replace=False)
    importance = permutation_importance(model, x_test[subset], y_test[subset], scoring="roc_auc", n_repeats=5, random_state=SEED)
    importances = sorted(({"feature": k, "label": labels[k], "auc_drop": round(float(importance.importances_mean[i]), 4)}
                          for i, k in enumerate(keys)), key=lambda item: -item["auc_drop"])

    # Deployed model learns from both cohorts. Inglewood is outside the city's registry, so it is scored by area and type.
    final = clone(candidates()[chosen]).fit(np.vstack([x_train, x_test]), np.concatenate([y_train, y_test]))
    median_age = {n: float(np.median([r["age_years"] for r in test_rows if r["category"] == n])) for n in CATEGORY_NAMES}
    areas = [str(f["properties"]["GEOID"]) for f in json.loads(areas_path.read_text())["features"]]
    weights = data.zcta_weights_2020()
    area_zip = {g: z for g in areas if (z := dominant_zip(g, weights)) in zip_values["forecast"]}
    # Age drives closure far more than place, so each type is scored as a new, typical and established business.
    ages = lambda n: {"new_business": 1.0, "typical": median_age[n], "established": 10.0}
    profiles = [{"age_years": age, "category": n, "profile": label} for n in CONSUMER_TYPES for label, age in ages(n).items()]
    forecast_zips = sorted(zip_values["forecast"])
    county_typical = {}
    for n in CONSUMER_TYPES:
        typical_rows = [{"age_years": median_age[n], "category": n}] * len(forecast_zips)
        county_typical[n] = round(float(np.median(final.predict_proba(business_matrix(typical_rows, forecast_zips, zip_values["forecast"]))[:, 1])), 4)
    forecasts = {}
    start = time.perf_counter()
    for g, z in area_zip.items():
        p = final.predict_proba(business_matrix(profiles, [z] * len(profiles), zip_values["forecast"]))[:, 1]
        scored = {(r["category"], r["profile"]): round(float(v), 4) for r, v in zip(profiles, p)}
        forecasts[g] = {"zip": z, "by_type": {n: {"new_business": scored[(n, "new_business")], "typical": scored[(n, "typical")],
                                                  "established": scored[(n, "established")], "county_typical": county_typical[n],
                                                  "typical_age_years": round(median_age[n], 1)} for n in CONSUMER_TYPES}}
    infer_seconds = time.perf_counter() - start
    scale = []
    for size in (10_000, 100_000, 1_000_000):
        tiled = np.resize(x_test, (size, x_test.shape[1]))
        begin = time.perf_counter()
        final.predict_proba(tiled)
        seconds = time.perf_counter() - begin
        scale.append({"rows": size, "seconds": round(seconds, 3), "rows_per_second": int(size / seconds)})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "model": "business-closure-v1",
        "question": "Will a business location in the City of Los Angeles close or move within five years?",
        "data": {"source": data.LA_BUSINESS_PAGE, "types_from_name_keywords": {k: sorted(v) for k, v in KEYWORDS.items()},
                 "type_counts": type_counts,
                 "label": "Location end date recorded within five years (closure or relocation of the registered location)."},
        "design": {"train": "Open on 2014-12-31; outcome by 2019-12-31; area features from ACS 2010–2014",
                   "test": "Open on 2019-12-31; outcome by 2024-12-31; area features from ACS 2015–2019; never used for training or model choice",
                   "deployment": "Inglewood businesses are not in the City registry, so the refit model scores a typical business of each type in each tract."},
        "sizes": {"train_businesses": int(len(y_train)), "test_businesses": int(len(y_test)),
                  "train_closure_rate": round(float(y_train.mean()), 4), "test_closure_rate": round(float(y_test.mean()), 4)},
        "model_selection": {"cv_auc_on_train_sample": cv, "chosen": chosen},
        "test": {"models": models, "consumer_facing_subset": consumer_subset, "baselines": baselines, "ablations": ablations,
                 "fairness_by_zip_majority_group": fairness, "permutation_importance": importances[:12]},
        "scalability": {"build_seconds": round(build_seconds, 1), "fit_seconds": timings, "area_type_scoring_seconds": round(infer_seconds, 3),
                        "prediction": scale},
        "limitations": ["Registry end dates mix closures, relocations and lapsed registrations.",
                        "The 2019–2024 test period includes the COVID shock, so closure rates differ from training.",
                        "Trained on the City of Los Angeles; Inglewood scores assume the same relationships hold nearby.",
                        "Area conditions are ZIP-level, so every tract in the same ZIP gets the same business outlook.",
                        "Business type comes from name keywords, so many businesses fall under Other and some are misclassified.",
                        "Scores describe a typical business of each type in an area, never a specific named business."],
    }
    output.write_text(json.dumps(report, indent=2) + "\n")
    forecast_output.write_text(json.dumps({"model": report["model"], "generated_at": report["generated_at"], "chosen": chosen,
                                           "test_auc": models[chosen]["auc"], "test_auc_consumer": consumer_subset["auc"],
                                           "test_businesses": int(len(y_test)), "horizon": "Five years from ACS 2020–2024 conditions",
                                           "tracts": forecasts}, indent=2) + "\n")
    return report


if __name__ == "__main__":
    result = run(Path("artifacts/prediction-business.json"), Path("data/curated/predictions-business.json"), Path("data/curated/areas.geojson"))
    best = result["test"]["models"][result["model_selection"]["chosen"]]
    print(f"Chosen {result['model_selection']['chosen']}: test AUC {best['auc']} {best['auc_95']}; sizes {result['sizes']}")
    for name, item in result["test"]["baselines"].items():
        print(f"  baseline {name}: AUC {item['auc']}")
