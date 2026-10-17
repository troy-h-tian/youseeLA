"""Attach model outputs to areas: forecasts for current views, backtests for historical ones."""

import json
from datetime import date
from pathlib import Path
from typing import Any

from youseela.contracts import Dataset, Prediction, PredictionFactor

# ACS 2020–2024 tables were published in December 2025; earlier assessment dates get the backtest instead.
FORECAST_AVAILABLE = date(2025, 12, 31)
TRACT_BASIS = ("LA County Census tracts: ACS income, rent, rent burden, housing, education, employment, race and ethnicity, "
               "previous-period rent and income trends, and ZIP Business Patterns amenity counts.")
BUSINESS_BASIS = ("City of Los Angeles business registrations (2014–2024 openings and closures), business age and type from its name, "
                  "and ZIP-level Census and business conditions. Inglewood is outside the City registry, so scores describe a "
                  "typical business of each type in this area's main ZIP, never a specific business.")


def tier(percentile: float) -> str:
    """Bands mirror the label: the model flags the county's top quarter for rent pressure."""
    return "higher" if percentile >= .75 else "moderate" if percentile >= .5 else "lower"


def factors(items: list[dict[str, Any]]) -> list[PredictionFactor]:
    return [PredictionFactor(feature=f["feature"], label=f["label"], effect=f["effect"], value=f["value"],
                             county_median=f["county_median"]) for f in items]


def tract_prediction(item: dict[str, Any], report: dict[str, Any], backtest: bool) -> Prediction:
    accuracy = (f"Tested on 2019→2024 outcomes it never saw: AUC {report['test_auc']:.2f}. Of the tracts it ranked in the "
                f"top 10%, {report['test_precision_top10']:.0%} truly had top-quarter rent pressure (vs {report['test_base_rate']:.0%} by chance).")
    outcome = None
    if backtest:
        happened = "did" if item["actual_top_quarter"] else "did not"
        outcome = (f"What happened: rent growth minus income growth was {item['actual_pressure']:+.0%} by 2020–2024, so this tract "
                   f"{happened} reach the county's top quarter.")
    return Prediction(key="rent_pressure_5yr", label="Rents outpacing incomes over five years", model="tract-rent-pressure-v1",
                      horizon="ACS 2015–2019 → 2020–2024" if backtest else "ACS 2020–2024 → next five years",
                      kind="backtest" if backtest else "forecast", probability=item["probability"],
                      county_percentile=item["county_percentile"], tier=tier(item["county_percentile"]),
                      accuracy=accuracy, basis=TRACT_BASIS, factors=factors(item["top_factors"]), outcome=outcome)


def business_prediction(item: dict[str, Any], report: dict[str, Any]) -> Prediction:
    accuracy = (f"Tested on {report['test_businesses']:,} LA City businesses open in 2019: AUC {report['test_auc']:.2f} overall and "
                f"{report['test_auc_consumer']:.2f} for food, retail and personal services. Business age matters most; "
                "neighborhood conditions add little.")
    by_type = {name: {k: v for k, v in values.items() if isinstance(v, (int, float))} for name, values in item["by_type"].items()}
    return Prediction(key="business_closure_5yr", label="Businesses closing or moving within five years", model="business-closure-v1",
                      horizon="Next five years", probability=None, accuracy=accuracy,
                      basis=BUSINESS_BASIS + f" ZIP {item['zip']}.", by_type=by_type)


def attach_predictions(dataset: Dataset, as_of: date, tract_path: Path, business_path: Path) -> Dataset:
    result = dataset.model_copy(deep=True)
    tract = json.loads(tract_path.read_text()) if tract_path.exists() else None
    business = json.loads(business_path.read_text()) if business_path.exists() else None
    backtest = as_of < FORECAST_AVAILABLE
    for area in result.areas:
        predictions = []
        if tract:
            source = tract["backtest"]["tracts"] if backtest else tract["tracts"]
            if area.id in source:
                predictions.append(tract_prediction(source[area.id], tract, backtest))
        if business and not backtest and area.id in business["tracts"]:
            predictions.append(business_prediction(business["tracts"][area.id], business))
        area.predictions = predictions
    return result
