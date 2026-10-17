# Temporal image search

No usable historical/current pairs found in the bounded Mapillary search. Three of 17 targeted requests failed, so this is not proof of absence. No paid vision calls were used.

## Historical fallback

Two inspected pairs show substantially comparable scenes; a third has partial overlap. All are from 2019/2020, not current conditions. No pair establishes gentrification or displacement.

### Pair 1: candidate

Residential street: matching houses, utility pole and street alignment. Lighting and cars differ; no displacement inference.

Camera separation: 0.75 metres.

- 2019-12-18: [Mapillary image](https://www.mapillary.com/app/?pKey=1608297156034468) — Mapillary contributor cfwarren3, CC-BY-SA 4.0.
- 2020-02-10: [Mapillary image](https://www.mapillary.com/app/?pKey=3357423691026871) — Mapillary contributor cfwarren3, CC-BY-SA 4.0.

### Pair 2: partial_overlap

Same corner but different viewing direction; limited overlap. Not a full-scene change pair.

Camera separation: 1.22 metres.

- 2019-12-18: [Mapillary image](https://www.mapillary.com/app/?pKey=138899648222807) — Mapillary contributor cfwarren3, CC-BY-SA 4.0.
- 2020-02-10: [Mapillary image](https://www.mapillary.com/app/?pKey=967595277324151) — Mapillary contributor cfwarren3, CC-BY-SA 4.0.

### Pair 3: candidate

Commercial street: matching parking structure and warehouse facade. Viewpoint/framing differ; needs frontage-level alignment.

Camera separation: 1.52 metres.

- 2019-05-20: [Mapillary image](https://www.mapillary.com/app/?pKey=3672049312922199) — Mapillary contributor victuallers, CC-BY-SA 4.0.
- 2020-01-09: [Mapillary image](https://www.mapillary.com/app/?pKey=795759134379829) — Mapillary contributor cfwarren3, CC-BY-SA 4.0.

## Next decision

Use explicitly historical pairs for a change-analysis prototype, or obtain matching current photos before claiming current observations. Keep visual feature extraction separate from conclusions about displacement.

Metadata and exact coordinates: `artifacts/temporal-imagery-search.json`. Originals remain in ignored `data/raw/images/`.

## Targeted search at known new construction

`python -m youseela.construction` locates new construction from the 2025 Assessor roll (effective year built 2019–2025) in a tract, groups parcels by Assessor map page, and searches Mapillary for photos taken before 2019 and after 2023 whose camera faces each site (within 60°). It pairs photos taken within 15 m and 30° of each other. Results are in `artifacts/construction-pairs.json`.

Downtown tract 06037601001 has one large development: 226 parcels on map page 4015-024, built 2020–2023, at about 33.96713, −118.34572. **Mapillary has no usable coverage of it.** No images exist within 250 m. The nearest 33 images are 324–550 m away, all captured on 2016-08-03, with none newer. The two single-parcel sites also returned nothing. A known-change pair for this site would need another imagery source.

Discovery changes in `sources/imagery.py`:
- **Panoramas** are excluded by default (`--include-panoramas` keeps them).
- **Date window:** `--captured-before` bounds the window.
- **Paging:** `--max-pages` follows result pages without saving token-bearing links.
- **Targeting:** `--target lon,lat` keeps only cameras facing a building.
- **Positions:** the computed (structure-from-motion) position and heading are preferred over raw GPS.
