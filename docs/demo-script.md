# Demo script

Lead with the **historical CLIP view**. It is the only view where scores combine Census data and images. The current view is honest about its gaps, but every tract there is unrated.

## Setup

```sh
npm --prefix web run build
npm --prefix web run preview -- --host 127.0.0.1 --port 4175
```

Open `http://127.0.0.1:4175/?data=clip`. If any data changed, rebuild it first with the commands in [clip-pipeline.md](clip-pipeline.md).

## Flow (about 5 minutes)

1. **Frame it (historical view).** Read the banner: "Historical multimodal prototype · as of 2020-12-31." Say that this is a 2019–2020 look back, not a current prediction.
2. **Business mode, tract 6014.01** (customers):
   - Score **16.1/100**, sensitivity range 16.1–66.1.
   - Open "Method and data limitations." With images zeroed, the score is 14.8, so **CLIP contributes 1.23 points**.
   - Open the evidence drawer to show the two dated Mapillary photos with attribution.
3. **Housing mode, tract 6009.11** (organizations):
   - Score **38.6/100**, range 38.6–63.6, driven by **63.7% rent burden**.
   - CLIP contributes **0.39 points**, because the photo pair barely differs. This shows that images influence the score without overriding the Census data.
4. **Historical photo comparison** ("Explore a historical photo comparison →"). Show the paired-image model comparison: matching landmarks and no clear structural change. Stress that it is an unreviewed scene comparison, not a prediction.
5. **Switch to "Current Census explorer"** for both journeys:
   - **Customer:** pick an area with a listed business, open the business card, then "Visit website" or directions.
   - **Organization:** Housing mode, compare two tracts, open evidence, then reach a tenant resource.
   - Point out the **unrated** states. Missing images are never scored as zero.
   - Open "Indicators" to show the Assessor, business-pattern and UDP context. It is labeled as not affecting the score.
6. **Scale.** Use the slide claim from [clip-evaluation.md](clip-evaluation.md): 1,000 areas, a 155 ms median build and 149 ms export/validation, and all 30 runs valid.

## Claims we can make

- Scores combine Census and image features, and the ablation shows each one's exact contribution (1.23 and 0.39 points).
- Every number traces to a dated, attributed source. Missing evidence shows as unrated, not zero.
- We tested our own signals and report what failed. Assessor indicators did not separate UDP-gentrifying tracts countywide (AUC 0.54–0.59, n=100; [context-sources.md](context-sources.md)).
- The pipeline scales to 1,000 areas with measured timings.

## Claims we must not make

- Any accuracy or prediction claim. No outcome labels exist, and the image test only matched its baseline.
- That a score means a tract *is* gentrifying, or anything about a specific business or household.
- That CLIP difference means redevelopment. It also picks up lighting, season and framing.

## Likely questions

- **"How accurate is it?"** Unmeasured. We say so, and we show the ablation and sensitivity ranges instead. A real test needs an independently observed later outcome.
- **"Why so few rated areas?"** Usable before/after photos are scarce. Our targeted search at a 226-parcel development built 2020–2023 found no Mapillary coverage within 250 m ([temporal-imagery-search.md](temporal-imagery-search.md)).
- **"Why is the image contribution so small?"** The weights are provisional assumptions (15–20% visual), and the available pairs show little change. More image weight does not always raise the score; see the sensitivity table in clip-evaluation.md.
- **"Why not Google Street View?"** Its terms restrict derived analysis and model evaluation. Mapillary is CC BY-SA.
