# Historical CLIP integration

Open `http://127.0.0.1:4175/?data=clip` in the local preview, or choose **Historical CLIP assessment** in the explorer. The default current Census view remains separate.

Frozen OpenAI CLIP ViT-B/32 encodes each photograph. Normalized embedding difference `(1 − cosine similarity) / 2` enters the weighted Census + imagery score directly. The feature measures appearance difference, including potential nuisance changes; it does not identify the direction or cause of neighborhood change. No custom CLIP training was performed.

The historical view covers all 29 Inglewood-area tracts with Census-only rough scores and model backtests (see prediction-model.md); two of them have real photo pairs. Tract 06037601401 supports one commercial score and tract 06037600911 supports one housing score. Boundary comparability uses a tolerance (at most 5 m shift and 0.1% area difference; `youseela boundary-check`, recorded in `artifacts/boundary-tolerance-check.json`). Tract 06037600911 failed exact equality only because its 2014 and 2019 boundaries differ by 0.11 m. One pair per area is a prototype coverage threshold, not a representative survey. The historical view contains no business profiles because present-day occupancy is not verified for the historical assessment date.

Install the optional local inference dependencies (model weights download on first use):

```sh
.venv/bin/python -m pip install -e '.[vision]'
.venv/bin/python -m youseela.vision.clip_features --manifest data/curated/clip-jobs.json
```

`clip-jobs.json` identifies permitted local image inputs. Paths are relative to the repository root. The feature export includes model revision, image hashes and cosine scores. The curated `clip-dataset.json` includes the generated features alongside Census data and source records. If regenerating features, replace its `clip_pairs` field with the new `clip-features.json` array before building; never silently keep outdated features after changing photographs.

Build the shipped historical dataset and evaluate:

```sh
.venv/bin/python -m youseela.cli build --input data/curated/clip-dataset.json --config config/clip-assessment.json --as-of 2020-12-31 --output data/exports/clip-historical.json
.venv/bin/python -m youseela.cli web-export --input data/exports/clip-historical.json --output web/public/data/clip-historical.json
.venv/bin/python -m youseela.clip_evaluation --sizes 10,100,1000 --runs 10
```

The public photos retain Mapillary attribution and CC BY-SA license links in the evidence drawer. This bounded exporter currently expects Mapillary JPEG filenames. New imagery providers need an explicit public image-path mapping. Feature and source dates are checked separately from image inference; caching does not authorize an image source.

See [presentation metrics](clip-evaluation.md) for the actual scale test, ablation, uncertainty and accuracy limitations. Local CLIP uses no paid inference API. Historical API vision comparisons are a separate model/task.
