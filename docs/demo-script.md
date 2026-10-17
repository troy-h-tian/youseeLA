# Demo script

Lead with the **trained model on the map**, then show the historical view's image-backed scores and backtest.

## Setup

```sh
npm --prefix web run build
npm --prefix web run preview -- --host 127.0.0.1 --port 4175
```

Open `http://127.0.0.1:4175/`. If any data changed, rebuild it first (see [prediction-model.md](prediction-model.md)).

## Flow (about 5 minutes)

1. **The map (Explore today).** Tracts are colored by the **5-year outlook**: predicted rent pressure, from light (lower) to red (top of LA County). Say: "This model was trained on 2014→2019 and tested on 2019→2024, a period it never saw."
2. **Housing support → a red tract** (for example Tract 6013.01):
   - The Outlook card shows **Higher pressure**, its county rank, and the three main reasons in plain numbers.
   - Open **How accurate is this?**: AUC 0.75, and 63% of top-10% flags were right versus 25% by chance.
3. **Toggle the legend to "Today's score".** Every tract now has a current pressure score. Ones without street images say "Rough score from Census data only".
4. **Support businesses → Dulan's Soul Food Kitchen:**
   - Show the photo, website and directions.
   - Scroll to **Business staying power**: the chance a new versus typical food business closes within five years.
   - The message for customers: new businesses are the most fragile.
5. **Historical analysis:**
   - **Commercial example (16.1)** and **Housing example (38.6)** are the image-backed scores. Each panel shows exactly how many points the photos add.
   - The **Model backtest** shows what the model predicted in 2019 and what actually happened, including its misses.
6. **Scale.** Re-scoring every LA County tract takes milliseconds (9.5M predictions per second). The business model trained on more than 1M business-years in 2 seconds.

## Claims we can make

- A predictive model tested on an unseen later period: **AUC 0.75, 2.5× lift** in its top 10%.
- **It beats every simple rule**, including "help where rent burden is high" and the UDP displacement map. The intuitive rules actually point the wrong way.
- **Business closure is hard to predict** (AUC 0.59–0.62). We show it honestly, by business type and age.
- **We tested fairness and ablations.** Race features add nothing measurable, and the model is weakest in Black-majority tracts.
- **Every score states its evidence:** Census-only, image-backed, or model forecast.

## Claims we must not make

- That a tract *will* gentrify or that anyone will be displaced. The model predicts rent outpacing income, a pressure proxy.
- Anything about a specific business closing.
- That race or any single factor causes the outcome. Explanations are associations.

## Likely questions

- **"Why logistic regression?"** It generalized better on the unseen period and is explainable. We disclose that we picked it after seeing test results.
- **"Why are the street images such a small part?"** Usable before/after photos are scarce: no Mapillary coverage within 250 m of a 226-unit development built 2020–2023. Images enter where they exist, with an ablation showing exactly how much they move the score.
- **"Why not Google Street View?"** Its terms restrict derived analysis. Mapillary is CC BY-SA.
