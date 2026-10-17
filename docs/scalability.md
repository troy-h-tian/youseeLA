# Scalability evaluation

Measured locally using synthetic inputs, ten runs per size after a warm-up. Environment and exact timings are recorded in [the report](../artifacts/scalability.json). Every output was parsed and validated; all measured runs completed without errors.

| Areas | Median score/build | Median export/validate | JSON size |
| ---: | ---: | ---: | ---: |
| 10 | 0.45 ms | 0.51 ms | 0.07 MB |
| 100 | 4.62 ms | 5.06 ms | 0.66 MB |
| 1000 | 53.32 ms | 99.04 ms | 6.60 MB |

Scoring includes geometry checks and construction of two mode assessments per area. Export includes serialization and public-schema validation. Fixture generation is excluded. These measurements test computational scaling, not prediction accuracy, real imagery coverage, or complete deployment capacity.

At 1,000 areas, the roughly 6.6 MB JSON payload merits frontend load/render measurement and likely pagination or area-specific loading. That is an inference from payload size; browser performance has not been measured.

Live image API telemetry now covers nine successful requests and eight cache hits; the machine-readable report includes measured latency. Estimated token cost for all nine calls is $0.00596 using published GPT-4.1 mini prices. This is not an invoice measurement. Download time, quotas, frontend rendering, and human review time remain unmeasured and may dominate the full workflow. The vision adapter logs per-request timings, usage, cache hits, and budget reservations. Reservations are not actual billed cost. To include later telemetry, rerun with `--telemetry data/raw/vision/telemetry.jsonl` (use the actual telemetry filename). Missing billed-cost measurements remain null; do not present inferred reservations as measured cost.

Reproduce:

```sh
python -m youseela.benchmark --sizes 10,100,1000 --runs 10 --output artifacts/scalability.json
```

Next evaluation: obtain adequate reviewed frontage coverage and time the two frontend modes using the same exported sizes. Retain provider/model, image count, run count, hardware, errors, and limitations with the results. Scaling to more areas also requires consistent image sampling and an audit of coverage bias.
