# youseeLA web explorer

React + TypeScript + Vite app with two equal modes: **Support businesses** (customers) and **Housing support** (organizations). It reads one precomputed JSON bundle. There is no backend, and no credentials reach the browser.

## Setup

```sh
npm --prefix web install
npx --prefix web playwright install chromium   # once, for browser tests
npm --prefix web run dev                       # http://localhost:5173/?data=fixture
```

| Command | What it does |
| --- | --- |
| `npm --prefix web run build` | Type-check and build to `web/dist` |
| `npm --prefix web run preview -- --host 127.0.0.1` | Serve the production build |
| `npm --prefix web run test -- --run` | Vitest: contract guard, ranking, mode switching, unrated display, evidence filtering |
| `npm --prefix web run test:e2e` | Playwright: both user journeys, failed images, keyboard use, mobile layout (desktop + Pixel 7) |
| `npm --prefix web run test:scalability` | Playwright: production-build UI timings → `artifacts/ui-scalability.json` |

## Data sources

- `public/data/demo.json` is the **real** bundle. Person A's pipeline writes it (`python -m youseela.cli build … --output web/public/data/demo.json`). Never edit it by hand. The app loads it by default.
- `public/data/fixture.json` is the **labeled acceptance fixture**: invented areas, businesses, images and scores. Open it with `?data=fixture`, or build with `VITE_DATA_SOURCE=fixture`. Whenever `data_kind` is `fixture`, a persistent "Demo fixture" banner is shown.
- The fixture covers the three required states: Area A is fully rated; Area B has a rated commercial assessment but unrated housing (too few residential images); Area C is unrated in both modes (no compatible ACS history). Area D adds the lower tier and has commercial imagery with P = 0, so the imagery adds no points.

## Data contract (schema v1)

`src/data/types.ts` is the TypeScript side of the shared contract. `src/data/load.ts` refuses any bundle that breaks these invariants. Please check these points against `contracts.py`:

- Bundle: `schema_version`, `generated_at`, `data_kind` (`real` or `fixture`), `methodology`, `areas`, `businesses`, `resources`, `evidence`.
- `methodology` has these fields: `config_version`, `summary`, `limitations[]`, `tier_bands {lower_below, moderate_below}`, `formulas {housing, commercial}`.
- Each area has a `housing` and a `commercial` assessment with `status`, `score`, `tier`, `unrated_reason`, `contributions[]`, `warnings[]`, `evidence_ids[]`, `config_version` and `coverage`.
  - When the status is `insufficient_evidence`, `score` and `tier` must be `null` and `unrated_reason` must be set.
- Each contribution carries `feature`, `label`, `weight`, `value` (0–1), `points` (100 × weight × value), `formula`, `numerator`, `denominator`, `evidence_ids` and `note`. When an assessment is unrated, `points` is `null`.
- Indicators carry `value`, `unit` (`share`, `usd`, `count` or `ratio`), `source_period`, `margin_of_error`, raw counts, `evidence_ids` and `unavailable_reason`.
- Businesses carry `rationale` (why the business is shown), `website_url`, and an optional `directions_url`. If `directions_url` is missing, the app builds an OpenStreetMap directions link from `location`.
- Resources carry `kind` (`housing` or `business`), `service_area`, and `area_ids`. An `area_ids` of `null` means the resource covers every pilot area.
- Evidence carries `evidence_type`, `frontage_class`, `image_url`, `reviewed`, `observations[]` (`present`, `absent` or `unclear`, plus `visible_count`) and `corrections[]`.
- Each mode's evidence drawer shows only the items listed in that assessment's `evidence_ids`.

## Scalability harness

`tests/scalability.spec.ts` measures three things, each repeated 3 times on the production preview at a 1280×800 viewport:

- initial render
- switching from Business to Housing mode
- selecting an area

It runs on the pilot bundle (`demo.json` if it exists, otherwise the fixture) and on 100- and 1,000-area synthetic bundles.

- **How bundles are loaded:** the test intercepts the app's normal `data/demo.json` request, so the shipped app has no benchmark route.
- **Synthetic data:** the bundles come from a seeded generator in `tests/support/synthetic.ts`. To use the Python generator's output instead, set `YOUSEELA_BENCHMARK_DIR` to a directory containing `bundle-100.json` and `bundle-1000.json`.
- **What is timed:** measure definitions are in `src/lib/perf.ts` and in the output JSON. Interaction timings stop at the first macrotask after the next animation frame, so about one frame (~16 ms) is the smallest value they can report.
- **What is not timed:** images load lazily from a controlled local route, so provider and network image delivery are excluded.
