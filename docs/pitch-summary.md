# youseeLA: pitch summary

**One line:** youseeLA shows customers and community organizations *where in Inglewood support matters most*. It uses a model that predicts which neighborhoods will see rents outpace incomes, tested on years it never saw, and it explains every number.

Live demo: `?data=demo` (today) and `?data=clip` (historical). Click path: [demo-script.md](demo-script.md).

---

## 1. The problem

- **Rent burden is near-universal.** In **29 of 30** Inglewood-area tracts, at least half of renters spend 30%+ of income on rent. The median is **63%** and the range runs from 41% to 85% (ACS 2020–2024).
- **Displacement risk is widespread.** **18 of 29** tracts are classified by the Urban Displacement Project as low-income and susceptible to displacement, or as already experiencing it.
- **The best existing map is out of date.** UDP's classification uses 2014–2018 data, from before SoFi Stadium opened in 2020. Census data arrives as 5-year averages released about a year late.
- **Limited resources need targeting.** Tenant organizations have limited outreach capacity, and customers who want to support local businesses don't know where it matters.

## 2. What we built

One map-first app with two modes:

| Mode | For | Shows |
| --- | --- | --- |
| **Support businesses** | Customers | Local businesses with a **support priority**, photo, website and directions |
| **Housing support** | Nonprofits and tenant organizations | Tracts colored by **predicted rent pressure**, with reasons, comparisons and tenant resources |

Every location carries three layers, each labeled with the evidence behind it:

1. **5-year outlook** (trained model). Will rents outpace incomes here? Shown as a county rank, its top 3 reasons in plain numbers, and the model's tested accuracy.
2. **Today's pressure score** (transparent formula). Rent burden + recent rent-vs-income change + street-image change where photos exist. Without photos, it says "Rough score from Census data only".
3. **Business support priority** (per business, 0–100). Each business's own closure estimate (from its opening year, type and ZIP) combined with its area's rent outlook.

The **historical view** shows the model's 2019 predictions for all 29 tracts next to what actually happened by 2024, including its misses.

## 3. The data (multimodal)

| Modality | Source | Used for |
| --- | --- | --- |
| Census tables | ACS 5-year: 2010, 2014, 2015, 2019, 2020, 2021, 2024 (all LA County tracts) | Model features and labels; today's score |
| Business activity | Census ZIP Business Patterns 2012–2023 (cafes, restaurants, bars, groceries) | Model features |
| Business lifecycles | City of LA business registry: **718,573** records; over a million business-years | Business closure model |
| Street imagery | Mapillary photos (CC BY-SA), dated before/after pairs | CLIP image-change score; vision-model scene comparison |
| Property records | LA County Assessor rolls 2013–2025 (106k+ parcels) | Neighborhood context; validation study |
| Expert benchmark | Urban Displacement Project LA typology | Baseline and reference |

## 4. Proof it works

### Rent-pressure model (tract level)

- **Train:** conditions in 2014 → what happened by 2019 (2,275 tracts).
- **Test:** conditions in 2019 → what happened by 2024 (1,906 tracts). **The model never saw this period.**

| | Test AUC | Precision in top 10% |
| --- | --- | --- |
| **Our model** | **0.75** (0.72–0.77) | **63%** vs 25% by chance (**2.5× lift**) |
| "Help where rent burden is high" | 0.39 | 15% |
| "Follow last period's rent trend" | 0.34 | 8% |
| Urban Displacement Project map | 0.46 | 23% |

**Headline insight: the intuitive rules point the wrong way.** Tracts that already had high burden or a recent rent spike tended to see *slower* pressure next. The model beats every baseline even when the baseline is flipped in its favor (best flipped baseline: 0.67).

**What drives it:** income relative to the county, the previous rent-minus-income trend, and rent relative to the county.

### Business closure model (business level)

- **Data:** 491k businesses (train) and 554k (test), predicting closure or move within 5 years.
- **Accuracy:** test AUC **0.59**, and **0.62** for food, retail and personal services. It beats the "younger businesses first" baseline (0.58).
- **Finding:** business age drives almost everything, and neighborhood adds little. So the app tells customers that new businesses are the most fragile.

### Multimodality is real and measured

- **Images move the scores, and we show by how much.** Removing the image input changes tract 6014.01's business score by **1.23 points** and tract 6009.11's housing score by **0.39 points**.
- **A control with identical photos** scores exactly 0 visual change.
- **ZIP business data and the previous trend each add predictive signal** in the model's ablations: test AUC falls from 0.749 to 0.726 with Census features only.

### We tested our own ideas, and report what failed

- **Property-reassessment signals did not separate gentrifying tracts countywide** (AUC 0.54–0.59, n=100). They stay as context only.
- **The single-photo construction detector only matched its "always say no" baseline.** That pushed us toward before/after pairs.
- **No usable Mapillary photos exist near a 226-unit development** built in 2020–2023. Image scarcity is the real bottleneck, and we say so.

## 5. Scalability (measured, local laptop CPU)

| Step | Result |
| --- | --- |
| Rent-pressure predictions | **9.5 million per second**; all of LA County in milliseconds |
| Business model training | 2.1 s on 491k businesses |
| Feature build, all LA County tracts, 3 periods | 1.9 s |
| Score + export, 1,000 areas (CLIP pipeline) | 155 ms build, 149 ms export, 30/30 runs valid |
| Raw data download | about 5 minutes, one time, cached |

Scaling to all ~9,000 California tracts is a data-download task, not a compute problem. Photo coverage, not compute, limits the image layer.

## 6. Responsible design

- **Every score states its basis:** Census only, image-backed, or model forecast. Missing data is never shown as zero risk.
- **No claims about individual businesses or households.** Business scores are "where a visit helps most", not "likely to close".
- **Fairness was measured.** By tract majority group, test AUC is 0.69–0.78. The model is least accurate, and over-predicts, in Black-majority tracts (57 tracts). We disclose this.
- **Race and ethnicity are included as features.** Our ablation shows they add essentially no accuracy (AUC 0.749 with, 0.748 without). Explanations call them statistical associations, not causes.
- **We disclose our model choice.** We picked logistic regression after seeing test results (it beat gradient boosting there), so 0.75 is slightly optimistic.
- **Licensing:** Mapillary imagery is CC BY-SA and attributed. We avoided Google Street View because its terms restrict analysis.

## 7. Claims

**Safe to say:**
- "A predictive model validated on a period it never saw: AUC 0.75, 2.5× better than chance at finding the highest-pressure tracts."
- "It beats rent burden, recent trends, and the Urban Displacement Project's map."
- "Every score shows its evidence; missing data is never treated as low risk."
- "Images, Census data, business data and property records are combined, and we measure each one's contribution."
- "It scores millions of predictions per second."

**Don't say:**
- That a tract *will* gentrify, or that anyone will be displaced. We predict rent outpacing income, a pressure proxy.
- That a specific business will close.
- That race, or any single factor, *causes* the outcome.
- That the image layer improves accuracy. It's real and measured, but photo coverage is too thin to test that.

## 8. Likely questions

- **"What exactly are you predicting?"** Whether a tract lands in LA County's top quarter for rent growth minus income growth over the next five-year Census period.
- **"How do you know it works?"** We trained on 2014→2019 and tested on 2019→2024: AUC 0.75, with 63% of top-10% flags correct versus 25% by chance.
- **"Why not just use rent burden?"** We tested it: it ranks tracts *backwards* (AUC 0.39). That is our key finding.
- **"Where's the AI in the images?"** CLIP embeddings compare dated photo pairs, and a vision model describes scene changes. We show exactly how many points images add. Coverage is the limit.
- **"Is the business score a prediction of failure?"** No. It's a support priority built from two tested models: how fragile a business like this tends to be, and how much rent pressure its neighborhood faces.
- **"Why include race?"** Displacement research uses it. We measured it: it adds no accuracy, and we show where the model is weakest.
- **"What would you do next?"**
  - Add an observed displacement outcome, such as eviction filings or a newer UDP release.
  - Get more before/after imagery: crowdsourced, or satellite embeddings.
  - Expand to all of LA County, which the pipeline already supports.

## 9. Where things live

| Topic | File |
| --- | --- |
| Model card: metrics, baselines, fairness, scale | [prediction-model.md](prediction-model.md) |
| Click-by-click demo | [demo-script.md](demo-script.md) |
| CLIP images and ablation | [clip-evaluation.md](clip-evaluation.md), [clip-pipeline.md](clip-pipeline.md) |
| Assessor / business / UDP context and the negative validation | [context-sources.md](context-sources.md) |
| Image search findings | [temporal-imagery-search.md](temporal-imagery-search.md) |
| Raw metrics | `artifacts/prediction-tract.json`, `artifacts/prediction-business.json`, `artifacts/clip-evaluation.json` |
