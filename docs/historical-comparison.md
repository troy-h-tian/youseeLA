# Historical commercial comparison

The real-data explorer now includes a separate historical evidence study. Follow “Explore a historical photo comparison” above the area explorer. It presents two original Mapillary photographs of the same commercial street, captured May 20, 2019 and January 9, 2020. Recorded camera positions are 1.52 metres apart, but framing differs.

Both images enter one structured vision-model request. The result identifies matching landmarks, earlier/later observations, uncertainty and limitations. The output is a scene comparison, not a gentrification prediction. It does not modify current area scores or establish present business conditions.

The initial result describes no clear structural change in the parking structure, uncertainty around the partly obscured right-hand building, and no clear street change. These remain unreviewed model claims. In particular, the model's “tree growth” wording is not established: foliage visibility could reflect framing or seasonal differences. The interface preserves the raw interpretation alongside an explicit review note.

## Evidence and reproduction

- Pair provenance: `data/curated/temporal-pair.json`.
- Job: `data/curated/temporal-job.json`.
- Raw structured result and image/prompt hashes: `data/exports/temporal-comparison.json`.
- Display snapshot: `web/src/data/historical-comparison.json`.
- Original images: `web/public/data/historical-images/`.

To repeat the exact job, copy the two published images into `data/raw/images/` using their unchanged filenames, then run:

```sh
python -m youseela.vision.temporal --manifest data/curated/temporal-job.json --output data/exports/temporal-comparison.json
```

This command requires the existing configured API key and spending cap. It reuses the shared budget ledger and cached result when present. Without a matching cache it sends one paid request containing two images; it does not retry failures automatically. Do not delete the spending ledger to reset the approved cap. If rerunning changes output, update the display snapshot before publishing; tests compare the snapshot, dates and image hashes against the saved result.

Both source images are attributed in the interface to their Mapillary contributors (victuallers and cfwarren3) under CC BY-SA 4.0. Originals are unchanged. The model-derived descriptions are also supplied under CC BY-SA 4.0; this data notice takes precedence over the software license for these assets.

## Limits and next evidence

No usable historical/current pair was found in the bounded search. This pair spans roughly eight months and does not test long-term displacement. A useful next sample would include independently labeled physical changes and comparable recent photos. Neither this one comparison nor its successful execution establishes predictive accuracy.

The initial paired-image request used 2,606 input tokens and 365 output tokens, an estimated $0.00163 at the configured model rates (not an invoice measurement). Shared reservations now total $1.10 of the $5 authorization.
