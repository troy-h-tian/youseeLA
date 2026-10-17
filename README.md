# youseeLA

An Inglewood prototype for exploring local businesses and neighborhood support needs through numerical housing data and reviewed street-level imagery.

The Python pipeline exports separate housing and commercial area assessments, component contributions, source evidence, business profiles, and local resources. These are experimental support-priority proxies, not validated predictions of displacement or business failure.

## Run locally

Requires Python 3.11 or newer.

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m youseela.cli fixture
python -m youseela.cli validate data/fixtures/bundle.json
python -m youseela.cli context   # optional; no credentials needed, a few minutes
python -m youseela.cli build
python -m pytest -q
```

`data/fixtures/bundle.json` contains clearly labeled synthetic examples for UI development. `data/exports/demo.json` contains real geography and verified business locations; its assessments are currently unrated because change estimates are uncertain, tract comparability needs verification, and reviewed image coverage is incomplete. Do not present fixture ratings as real findings.

## Data and integration

- [Person A setup and evidence workflow](docs/person-a.md)
- [Frontend handoff and missing-data behavior](docs/frontend-handoff.md)
- [Scalability evaluation](docs/scalability.md)
- [Historical evidence and coverage findings](docs/evidence-status.md)
- [Assessor, business-pattern and UDP benchmark context](docs/context-sources.md)
- [Demo script](docs/demo-script.md)
- [Public JSON Schema](contracts/bundle.schema.json)

Configuration lives in `config/assessment.json`. Images affect scores through a corroborated physical-change feature combined with numerical affordability pressure. Missing or ambiguous evidence produces an unrated result. Housing context does not establish an individual business's financial condition.

Credentials belong in an ignored `.env` file copied from `.env.example`. Live image analysis also requires an explicitly selected model, source permissions, and a positive budget reservation. Raw images, API responses, and credentials stay outside version control. The integrated React explorer lives in `web/`.

## Run the explorer

```sh
python -m youseela.cli web-export
npm ci --prefix web
npm --prefix web run dev -- --host 127.0.0.1
```

Open the printed local URL for real data. Append `?data=fixture` only for the visibly labeled synthetic score demonstration. The real data supports business discovery and housing context; it does not yet support vulnerability rankings.

For production verification, run `npm --prefix web run build`. Browser tests require `cd web && npx playwright install chromium` once; then run `npm --prefix web run test:e2e` from the repository root.
