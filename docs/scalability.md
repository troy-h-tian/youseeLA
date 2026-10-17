# Scalability evaluation

Measured locally using synthetic inputs, ten runs per size after a warm-up. Environment and exact timings are recorded in [the report](../artifacts/scalability.json). Every output was parsed and validated; all measured runs completed without errors.

| Areas | Median score/build | Median export/validate | JSON size |
| ---: | ---: | ---: | ---: |
| 10 | 0.45 ms | 0.51 ms | 0.07 MB |
| 100 | 4.62 ms | 5.06 ms | 0.66 MB |
| 1000 | 53.32 ms | 99.04 ms | 6.60 MB |

Scoring includes geometry checks and construction of two mode assessments per area. Export includes serialization and public-schema validation. Fixture generation is excluded. These measurements test computational scaling, not prediction accuracy, real imagery coverage, or complete deployment capacity.

At 1,000 areas, payload size and initial rendering grow materially. Pagination or area-specific loading is a reasonable next improvement; the demo does not need distributed infrastructure.

Live image API telemetry now covers nine successful requests and eight cache hits; the machine-readable report includes measured latency. Estimated token cost for all nine calls is $0.00596 using published GPT-4.1 mini prices. This is not an invoice measurement. Download time, quotas, and human review time remain unmeasured and may dominate the full workflow. The vision adapter logs per-request timings, usage, cache hits, and budget reservations. Reservations are not actual billed cost. To include later telemetry, rerun with `--telemetry data/raw/vision/telemetry.jsonl` (use the actual telemetry filename). Missing billed-cost measurements remain null; do not present inferred reservations as measured cost.

Reproduce:

```sh
python -m youseela.benchmark --sizes 10,100,1000 --runs 10 --output artifacts/scalability.json
```

Next evaluation: obtain adequate reviewed frontage coverage and measure image delivery and human review time. Retain provider/model, image count, run count, hardware, errors, and limitations with the results. Scaling to more areas also requires consistent image sampling and an audit of coverage bias.

## Browser measurements

Production build, Chromium, 1280×800 viewport, three repetitions per dataset. Full environment and measurement definitions are in [the browser report](../artifacts/ui-scalability.json). These run against the frontend display contract; the 100/1,000-area inputs are separately generated synthetic fixtures, not the Python benchmark files. Image delivery is excluded.

| Dataset | Initial render median/max | Mode switch median/max | Area selection median/max |
| --- | ---: | ---: | ---: |
| pilot (real) | 61.5/64.2 ms | 22.6/23.2 ms | 15.2/15.5 ms |
| synthetic-100 | 78.7/80 ms | 22.4/23 ms | 15.1/15.9 ms |
| synthetic-1000 | 328.8/339.6 ms | 51.8/55.2 ms | 14.5/14.5 ms |

Reproduce with `npm --prefix web run test:scalability`. Local browser measurements are not an internet latency or production hosting guarantee.

## API cost projection, not measured bills

Nine successful calls cost an estimated $0.00596 based on returned token usage and published rates. At six calls per area and the same image/output mix, the estimates are $0.040 for 10 areas, $0.397 for 100, and $3.973 for 1,000. These exclude retries and additional historical corroboration. Sparse or empty observations in this pilot may make its average cost unrepresentative of richer images. No bulk calls were sent to obtain these projections. Runtime extrapolation is omitted because concurrency and provider quotas were not measured.
