# Person A: data and model workflow

Start from the repository root with the virtual environment activated. Keep all secrets in `.env`; never include it in a commit. If `.env` already exists, edit it rather than copying over it.

## 1. Access

Use `.env.example` as the template. Activate a Census key, create a Mapillary developer token, and configure an OpenAI API key. Run `python -m youseela.cli env-status` to check presence without printing values. The vision adapter currently supports OpenAI only. Choose a currently available image-capable model in `VISION_MODEL` before invoking it.

`VISION_BUDGET_USD` and `VISION_MAX_COST_PER_REQUEST_USD` default to zero. No live inference works until both are positive. The per-call value is a conservative reservation you choose using provider pricing; it is not a guaranteed billing cap. Configure provider-side spending controls too. Failed requests retain their reservation because billing can be uncertain. The ledger and telemetry live under ignored `data/raw/vision/`.

## 2. Numerical data

```sh
python -m youseela.cli census --year 2024 --output data/raw/acs-2024.json
python -m youseela.cli census --year 2021 --output data/raw/acs-2021.json
python -m youseela.cli prepare --latest data/raw/acs-2024.json --prior data/raw/acs-2021.json
```

The checked-in geography contains full 2020 Census tracts that intersect Inglewood with positive area. Full tract estimates can include residents outside city limits. Refresh with `python -m youseela.cli geography` only when needed.

Check equivalent tract boundaries for the two ACS periods before rerunning prepare with `--geography-verified`. Matching IDs alone do not prove equivalent boundaries. Without this flag, affordability pressure stays missing. The overlapping five-year periods describe pooled estimates, not independent yearly observations. Margins of error can also make pressure uninterpretable; do not bypass this gate to obtain a rating.

For a smaller pilot, append `--area-ids 06037601001 06037601303 06037601100`. These contain the five curated businesses. Preparation combines the numerical data with `data/curated/businesses.json`, `resources.json`, and `evidence.json`.

## 3. Imagery

```sh
python -m youseela.cli images --bbox=-118.356,33.958,-118.351,33.963 --captured-after 2023-10-18
```

This discovers metadata; it does not establish permission or adequate coverage. Check capture dates, coordinates, attribution, license, and whether analytical use and local caching are allowed. Google Street View analysis is not cleared for this project. Download permitted JPEG/PNG files to ignored `data/raw/images/`; the vision adapter accepts files up to 5 MB.

Create a JSON list of jobs at `data/raw/images/manifest.json`. Each job has `image_path` (relative to the manifest), `analysis_permitted`, `cache_permitted`, and `evidence`. Set permission flags only after verifying the source conditions. Evidence fields are defined in `src/youseela/contracts.py`; each image needs a unique ID, tract ID, housing or commercial mode, public source URL, capture date, attribution, license, site ID, latitude, longitude, `reviewed: false`, `data_kind: "real"`, and an empty observations list. Never put a token-bearing download URL in public evidence.

```sh
python -m youseela.cli vision --manifest data/raw/images/manifest.json
```

Output in `data/raw/vision/drafts.json` is unreviewed. A human must check observations against the photo, align frontage IDs across images, and resolve uncertainty. Visible physical work marked present needs a matching earlier image or official project record, linked through `corroboration_ids`. Project records must explicitly identify the same `site_id` or list the site in `applies_to_site_ids`. Earlier images must match site and mode. Cite the actual evidence; do not invent corroboration.

Collect at least three sites separated by 25 meters and five assessable unique frontages for each tract/mode. Apply the same sampling rule to compared areas. Current samples must be within 1,095 days of the assessment date. Do not cherry-pick images to produce a higher score. Add checked image and project records to `data/curated/evidence.json`, setting `reviewed: true` only after review. Rerun prepare to incorporate them.

## 4. Export and verify

```sh
python -m youseela.cli build
python -m youseela.cli validate data/exports/demo.json
python -m pytest -q
python -m youseela.benchmark --sizes 10,100,1000 --runs 10 --output artifacts/scalability.json
```

Check both mode scores, explanations, map positions, dates, and support links in the teammate's UI. Verify that missing evidence displays as unrated. The fixture tests demonstrate that relevant image changes affect the formula; they do not demonstrate predictive accuracy. Live Census retrieval and image extraction have now been exercised. A rated real-data result remains unverified: the selected change estimates are uncertain and the imagery still needs adequate frontage coverage and human review.
