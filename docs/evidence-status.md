# Evidence status: historical fallback and recent search

The current evidence supports a dated exploratory demonstration, not a defensible ranking of business displacement risk. No real scores have been forced through the missing-data gates.

## Available artifacts

- `data/exports/demo.json`: 30 real areas, 60 Census source records, five verified current business locations, and local resources. Current housing and commercial assessments remain unrated.
- `data/exports/historical-context.json`: one downtown tract, 2014 and 2019 ACS context, with a Census 2010 boundary obtained from the official TIGERweb point query. It is a retrospective presentation of pooled historical conditions, not a forecast or backtest. Tract equivalence across ACS vintages still needs verification.
- `data/exports/evidence-review.json`: eight unreviewed image drafts: three downtown photographs from December 2019 and five recent candidates. This is a review packet, **not** a scored Bundle. Do not ingest it as approved evidence.
- `artifacts/image-coverage.json`: 37 initial city-intersecting queries and 28 smaller retries. They returned 118 unique recent image candidates inside the city across four tracts. Failures and 100-image limits mean this is not an exhaustive inventory.

The local `.Codex/evidence-review.html` displays images and draft observations and can download reviewer decisions. It remains ignored, as do the source images and raw API responses. Its browser interactions have not been verified: browser automation rejected the local file URL. Decisions never automatically approve scoring evidence.

## What the data says

The downtown historical tract has an estimated 51.8% of households with computable rent-to-income ratios spending at least 30% of income on rent in the 2015–2019 ACS. This is housing affordability exposure; it is not a probability of displacement. The change in rent relative to income has a sensitivity interval spanning zero, so the combined rating is withheld.

Recent samples inspected include freeway scenes, an obstructed intersection, a stadium interior, and a wall. Recent capture dates alone do not establish usable storefront or housing coverage. Three separated camera positions can still depict the same frontage; humans must resolve duplicates and target-building locations.

Historical photos are more relevant to downtown street frontage, but remain dated and unreviewed. The current business directory does not establish which businesses operated at those locations in 2019. Do not combine historical photo conditions with current listings as evidence of present business distress.

## Next useful step

Review the historical image observations and identify unique assessable frontages. Use a dated evidence walkthrough for the hackathon while explaining why uncertainty prevents a combined score. A genuine current ranking requires better imagery and interpretable numerical change evidence; switching dates alone does not solve either requirement. Synthetic rated fixtures remain available strictly for demonstrating interface behavior and model sensitivity.

## Rights and cost

Each image record carries its contributor and Mapillary source link. Original imagery remains under CC-BY-SA 4.0. Image-derived observations in the review packet are also provided under CC-BY-SA 4.0; this data notice takes precedence over the repository software license for those observations. Preserve attribution and describe modifications when distributing derived material. See the [Mapillary imagery license](https://help.mapillary.com/hc/en-us/articles/115001770409-CC-BY-SA-license-for-open-data).

Nine successful vision requests used an estimated $0.00596 in tokens under [published GPT-4.1 mini pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini); actual invoice charges were not queried. Eight identical jobs subsequently hit the local cache without additional API requests. The $5 authorization remains in effect; reservations totaled $0.45 and are deliberately more conservative than estimated token charges.
