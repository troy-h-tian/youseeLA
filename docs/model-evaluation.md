# Model evaluation

The area assessment is an experimental weighted heuristic. No independently labeled displacement outcomes are available, so area prediction accuracy is unknown.

## Image observation pilot

Twelve historical Inglewood images were labeled by one human before model predictions were shown. The reference contains eleven absent-work images and one unusable image (the reviewer confirmed no housing fronts were visible). There are no construction-positive reference examples.

- Human-label agreement: 11/12 (91.7%).
- Always predict absent baseline: 11/12 (91.7%). The model does not beat this baseline on overall agreement.
- One construction false alarm among eleven absent-work images (9.1%).
- One unusable image correctly identified; ten absent-work images correctly identified.
- Construction recall cannot be estimated without positive examples.

This measures agreement on a small, spatially clustered sample, not gentrification prediction accuracy. The prompt was aligned to the housing/commercial labeling instructions before inference. The images and labels are a development pilot, not a sealed independent test set; future prompt tuning requires a separate evaluation sample.

Source labels: `data/curated/image-evaluation-labels.json`. User clarification: `data/curated/image-evaluation-clarification.json`. Predictions: `data/exports/image-evaluation-drafts.json`. Metrics and prompt hashes: `artifacts/image-evaluation.json`. Image-derived drafts retain contributor attribution and CC-BY-SA 4.0 notices. Draft observations remain unreviewed and are not approved scoring evidence.

Reproduce without paid inference:

```sh
python -m youseela.evaluation --labels data/curated/image-evaluation-labels.json --predictions data/exports/image-evaluation-drafts.json --output artifacts/image-evaluation.json
```

## What this changes about interpretation

Construction visibility alone is a weak support-priority indicator: absence in a snapshot does not establish absence of neighborhood pressure, and visible work does not establish harmful redevelopment. The current formula requires independent corroboration for positive redevelopment observations. Numerical pressure remains separate from visual evidence. The pilot does not validate construction as a predictor of displacement or justify increasing its weight. A broader visual change model would need comparable images over time and independent outcome evaluation.

## Numerical sensitivity

Version experimental-v2-sensitivity permits provisional point estimates when rent/income margins of error span zero change, provided all geography and imagery gates pass. It exports a sensitivity range, not a statistical confidence interval. Rent burden, imagery and weights are held fixed while rent/income inputs vary within their reported margins of error. The UI shows ranges and avoids ranking when they overlap. Missing imagery still produces an unrated assessment.

Four historical pilot tract polygons were verified equal between the official ACS 2014 and ACS 2019 geographic services. This does not verify current-period boundaries. Historical exports remain unrated while individual visual observations and coverage await review.

## Runtime and spending

See `docs/scalability.md` for the separate runtime evaluation. Across the initial batch and this evaluation, 21 successful image requests used approximately $0.01430 in token charges at the configured pricing; actual billed charges were not queried. Conservative budget reservations total $1.05 against the $5 cap. Runtime performance and unit test pass rates are not model accuracy.
