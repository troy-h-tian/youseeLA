# Predictive models

Two trained models, each tested on a later period it never saw. They are separate from the hand-weighted "today's pressure score": the map shows both, labeled.

```sh
pip install -e '.[model]'
python -m youseela.prediction.data            # downloads and caches raw inputs (needs CENSUS_API_KEY); ~5 minutes
python -m youseela.prediction.tract_model     # ~30 seconds
python -m youseela.prediction.business_model  # ~4 minutes
python -m youseela.cli build && python -m youseela.cli web-export
```

Full metrics: `artifacts/prediction-tract.json` and `artifacts/prediction-business.json`. Predictions shipped to the app: `data/curated/predictions-*.json`.

## 1. Tract model: will rents outpace incomes?

**Question.** Will a tract land in LA County's top quarter for *rent growth minus household-income growth* over the next five-year Census period?

**Design.**
- **Train:** conditions in ACS 2010–2014 predict the outcome in 2015–2019 (2,275 tracts).
- **Test:** conditions in 2015–2019 predict the outcome in 2020–2024 (1,906 tracts whose boundaries match one-to-one across the 2010 and 2020 tract definitions). The test period was never used for training.
- **Forecast:** conditions in 2020–2024 → next five years, for all 2,466 tracts, after refitting on both labeled periods.

**Features (24).**
- **Census:** income, rent and home value relative to the county median; rent burden; renter share; education; poverty; vacancy; unemployment; housing age; population.
- **Race and ethnicity:** Hispanic, Black, White and Asian shares.
- **Previous-period trend:** rent and income growth.
- **ZIP business data:** amenity density, establishment density, amenity share, and two-year growth (Census ZIP Business Patterns).

**Model.** Logistic regression. Cross-validation on the training period preferred gradient boosting (AUC 0.772 vs 0.756), but on the test period logistic regression generalized better (0.749 vs 0.702) and is directly explainable. **This deployment choice was made after seeing test results, so its test numbers are slightly optimistic.** Both models' results are in the artifact.

### Test results (2019 → 2024, unseen)

| | AUC (95% CI) | Precision in top 10% | Lift |
| --- | --- | --- | --- |
| **Logistic regression (deployed)** | **0.749** (0.724–0.774) | **63%** (56–70%) | **2.5×** |
| Gradient boosting | 0.702 (0.680–0.731) | 52% | 2.1× |
| Baseline: rent burden today | 0.385 (0.615 if flipped) | 15% | |
| Baseline: previous-period trend | 0.338 (0.663 if flipped) | 8% | |
| Baseline: the app's current formula | 0.333 (0.668 if flipped) | 9% | |
| Baseline: UDP typology (2018) | 0.455 (0.545 if flipped) | 23% | |
| Random | 0.500 | 25% (base rate) | 1.0× |

**Main finding.** The intuitive rules are backwards. Tracts that already have high rent burden, or recent fast rent growth, tended to see *slower* rent-over-income growth next: some of this is real catch-up and some is noise in tract estimates. The model beats every baseline even when the baseline's direction is flipped in its favor.

Brier score 0.161 vs 0.188 for always predicting the base rate. Calibration is slightly high: the top tenth predicts 67% and observes 63%.

**What drives it** (drop in test AUC when shuffled): income relative to county (0.19), previous-period rent-minus-income growth (0.14), and rent relative to county (0.12). Everything else is under 0.02.

**Ablations** (test AUC):
- Without race: 0.748
- Without ZIP business data: 0.747
- Without trend: 0.732
- Census only: 0.726

Race and ethnicity features add essentially nothing. They were included at the team's direction and appear in per-tract explanations as statistical associations.

**By tract majority group** (test):

| Group | Tracts | Observed rate | Mean predicted | AUC |
| --- | --- | --- | --- | --- |
| Hispanic or Latino | 1,107 | 24% | 27% | 0.734 |
| White | 572 | 26% | 33% | 0.780 |
| Asian | 170 | 28% | 34% | 0.765 |
| Black | 57 | 21% | 35% | 0.685 |

The model is least accurate, and most over-predicts, in the 57 Black-majority tracts. Treat those outlooks with extra caution.

**Inglewood backtest.** The historical view shows the train-only model's 2019 prediction next to what happened by 2024. Five of 29 Inglewood-area tracts reached the top quarter, and the model does not catch all of them. Tract 6009.11 is shown as a miss.

## 2. Business model: will a business close or move within five years?

**Data.** City of Los Angeles business registrations: 491,157 businesses open on 2014-12-31 (train) and 554,234 open on 2019-12-31 (test), with five-year outcomes.

**What the data forced:**
- **No coordinates or industry codes.** The City strips them from closed accounts, so using either would leak the outcome.
- **Location is the ZIP code**, and **type comes from name keywords** (CAFE, TACOS, SALON, MARKET and so on). Both are kept for open and closed businesses alike. About 6% of businesses get a named type; the rest are "Other".

**Features:**
- years at this location
- type
- the same 24 area features, measured at ZIP level

### Test results (2019 → 2024, unseen)

| | AUC (95% CI) | Precision in top 10% |
| --- | --- | --- |
| **Gradient boosting (deployed; cross-validation choice)** | **0.590** (0.588–0.592) | 23% (base rate 17%) |
| Same, food / retail / personal services only (35,568) | 0.621 (0.609–0.632) | 14% (base rate 7%) |
| Baseline: younger businesses first | 0.576 | 21% |
| Baseline: ZIP's 2015–2019 closure rate | 0.501 | 17% |

**Main finding.** Business age drives almost everything (permutation AUC drop 0.068). Neighborhood features add nothing measurable: without them, AUC is still 0.590. The app therefore shows the business outlook **by type and age**, not as a map color, and its message for customers is that new businesses are the most fragile.

**Calibration.** Predictions run high (mean 25% vs observed 17%). Recent closures may be recorded late in the registry, and 2019–2024 includes COVID.

**Fairness** (AUC by ZIP majority group): 0.58–0.60 across groups.

**Applied to Inglewood.** Inglewood is outside the City registry. Scores describe a typical business of each type in each tract's main ZIP: never a named business.

## Scalability (local CPU, single process)

| Step | Measured |
| --- | --- |
| Tract features, all LA County, three periods | 1.9 s |
| Tract model fit | 0.007 s (logistic regression) |
| Tract predictions | 9.5 million rows/s (1M synthetic rows in 0.11 s) |
| Per-tract explanations, 30 tracts | 0.008 s |
| Business data build (1M+ business-years) | 11.7 s |
| Business model fit (491k rows) | 2.1 s |
| Business predictions | about 745,000 rows/s (1M rows in 1.3 s) |
| Raw data download (one-time, cached) | about 5 minutes; dominated by the City API and Census files |

Re-scoring every tract in the county takes milliseconds, and extending to all of California's roughly 9,000 tracts would be data download, not compute. Prediction speed is measured on synthetic copies of real rows.

## Limitations

- ACS tract estimates are noisy, so some "rent surges" are sampling error. That caps achievable accuracy.
- Rent outpacing income is a **proxy for displacement pressure**, not observed displacement.
- Registry end dates mix closures, relocations and lapsed registrations.
- Both test periods include COVID-era shocks.
- Explanations show how much each value moves the prediction relative to the typical tract. They are associations, not causes.
