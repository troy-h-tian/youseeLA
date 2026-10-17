# Neighborhood-change context and benchmark

Three non-image sources add tract-level context. These indicators are **not score inputs**. `scoring.py` never reads them. Before any of them is weighted, the team must decide that explicitly and compare the result against the benchmark below.

```sh
python -m youseela.cli context   # writes data/curated/context.json and artifacts/context-benchmark.json
python -m youseela.cli build     # attaches context to areas when data/curated/context.json exists
python -m youseela.cli web-export
```

No credentials are needed. Raw downloads are cached in the ignored `data/raw/context/` folder, and re-running the command reuses them.

## Sources

| Source | What it measures | Precedent | Granularity |
| --- | --- | --- | --- |
| [Urban Displacement Project LA typology](https://github.com/urban-displacement/displacement-typologies) (commit pinned in `sources/typology.py`) | A Census-based gentrification and displacement category per tract, ACS 2014–2018 | Huang et al. (2023) validated street-view detections against prior census-based gentrification measures | 2010 tract, matched to 2020 tracts |
| [LA County Assessor roll](https://data.lacounty.gov) (rolls 2020 and 2025) | Share of taxable parcels whose Prop 13 land base year falls in the roll's five-year window (a market sale or new construction resets it), and share whose effective year built falls in that window (new construction or major renovation) | Ilic et al. (2019) and Mueller et al. (2026) validated against building permits; Inglewood is outside LADBS permit data, so these reassessment events stand in for permits | Parcel centroid → 2020 tract |
| [Census ZIP Business Patterns](https://www.census.gov/programs-surveys/cbp.html) (2019, 2023) | Cafes (722515), full-service restaurants (722511), bars (722410) and groceries (445110) | Glaeser, Kim & Luca (2018) found these Yelp categories lead gentrification | ZIP; each tract gets the 2020 ZCTA covering most of its area |

## Safeguards

- **UDP labels** attach only when the 2020 tract and a 2010 tract each cover at least 95% of the other's land, using the Census relationship file. Split tracts (for example 06037604200) get no label instead of a guessed one. Combined categories are also skipped.
- **Assessor shares** are withheld for tracts with fewer than 50 taxable parcels. Exempt and public parcels are excluded because their base years do not reset on sale. The default windows (base years 2016–2020 and 2021–2025) do not overlap, and `collect` rejects overlapping windows.
- **Business counts** describe a whole ZIP and repeat across every tract mostly inside it. Their evidence is commercial-mode only.
- **Provenance.** Each value cites an evidence record with its source, date, attribution and license. UDP data is GPL-3.0; only per-tract category labels are redistributed here.

## First results (30 tracts)

See `artifacts/context-benchmark.json` for group medians.

- **UDP labels.** 29 of 30 tracts match a 2010 tract. The labels are 14 LISD, 5 SMMI, 5 ARE, 4 OD (ongoing displacement) and 1 SAE. **No Inglewood tract is labeled gentrifying (ARG/EOG/AdvG) in the 2014–2018 data.** As a result, the benchmark can check displacement-related groups but cannot validate gentrification detection directly.
- **Assessor data across groups.** Tract-level reassessment rates are about 10–20% in both windows. Group medians differ by only about 1 percentage point, so there is no clear separation by UDP group.
- **Downtown outlier.** Tract 06037601001 is the clear exception. Reassessed parcels rose from 16% to 37%, and built-or-renovated parcels from 0% to 22%, because taxable parcels grew from 543 to 753 with about 165 built in 2021–2022. This is real new construction, but per-parcel counting magnifies multi-unit projects. It is also the tract with the retained 2019 downtown photos, which makes it a good candidate for before/after image comparison.
- **ZIP amenity counts.** Most ZIPs rose modestly from 2019 to 2023. In 90302, amenity establishments went from 6 to 17 (cafes, restaurants and groceries). Counts below about 10 are too small to read as a trend.

## Countywide validation

Inglewood has no UDP-gentrifying tracts, so `python -m youseela.context_validation` tests the assessor indicators elsewhere in LA County. It compares 50 randomly sampled UDP-gentrifying tracts (34 EOG, 16 AdvG) with 50 low-income non-gentrifying tracts (LISD), using base-year windows 2009–2013 and 2014–2018 and seed 20261017. All 100 tracts were analyzed and no queries failed. Full results are in `artifacts/context-validation.json`.

| Indicator | AUC | 95% bootstrap | Median, gentrifying vs comparison |
| --- | --- | --- | --- |
| Reassessed share, 2014–2018 | 0.54 | 0.43–0.65 | 19.2% vs 17.9% |
| Change in reassessed share | 0.59 | 0.47–0.70 | −0.3 vs −1.2 points |
| Built or renovated share | 0.54 | 0.43–0.66 | 0.4% vs 0.2% |
| Change in built or renovated share | 0.54 | 0.43–0.65 | 0 vs 0 |
| Recent sale value per sq ft growth* | 0.55 | 0.44–0.67 | +44% vs +42% |

\*UDP's definition partly includes price growth, so this was expected to separate the groups by construction.

**Conclusion:** every interval includes 0.5, so these tract-level assessor indicators do not detect UDP gentrification. Even the price signal failed, and it should have separated the groups by construction. That points to tract-level turnover and value aggregates being dominated by countywide market cycles, such as the post-2009 recovery that raised values everywhere. They should stay unscored context. The downtown Inglewood construction spike remains a valid local observation, but it is not evidence that the indicator ranks tracts well.

## Known confounds

- **Reassessment rates** move with interest rates and the post-2022 sales slowdown, as well as with neighborhood change. A new condo building adds many newly assessed parcels at once, as in tract 06037601001.
- **Effective year built** is the Assessor's adjusted age. It is not a permit record.
- **ZIP business counts:** ZIP Business Patterns counts establishments, not openings or closures, and 2019–2023 spans COVID. ZIP codes and ZCTAs are not identical.
- **UDP** is itself a model built from Census data, not observed displacement. It predates SoFi Stadium (opened 2020).
