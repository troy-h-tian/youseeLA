"""Validate public artifacts before the frontend can consume them."""

from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

from shapely.geometry import Point, shape

from youseela.contracts import Area, Bundle, Dataset, Evidence
from youseela.scoring import AssessmentConfig, assess


def build_bundle(dataset: Dataset, config: AssessmentConfig, as_of: date) -> Bundle:
    if any(not e.reviewed for e in dataset.evidence):
        raise ValueError("All evidence must be reviewed before public export; keep draft model results separate")
    if dataset.data_kind == "real" and any(x.data_kind != "real" for x in [*dataset.evidence, *dataset.businesses, *dataset.resources]):
        raise ValueError("Fixture records cannot be relabeled as real")
    by_area: dict[str, list[Evidence]] = defaultdict(list)
    geometry = {a.id: shape(a.geometry) for a in dataset.areas}
    for boundary in geometry.values():
        if not boundary.is_valid or boundary.is_empty or boundary.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Areas need valid nonempty polygon boundaries")
    for item in dataset.evidence:
        if item.area_id not in geometry:
            raise ValueError("Evidence references an unknown area")
        if item.source_date > as_of:
            raise ValueError("Evidence capture/source date is after the assessment date")
        if item.latitude is not None and item.longitude is not None and not geometry[item.area_id].covers(Point(item.longitude, item.latitude)):
            raise ValueError("Located evidence is outside its assigned area")
        by_area[item.area_id].append(item)
    for business in dataset.businesses:
        if business.area_id not in geometry or not geometry[business.area_id].covers(Point(business.longitude, business.latitude)):
            raise ValueError("Business is outside its assigned area")
    areas = [Area(**area.model_dump(),
                  housing=assess(area.id, "housing", area.indicators, by_area[area.id], config, as_of),
                  commercial=assess(area.id, "commercial", area.indicators, by_area[area.id], config, as_of))
             for area in dataset.areas]
    return Bundle(generated_at=datetime.now(timezone.utc), assessed_as_of=as_of,
                  data_kind=dataset.data_kind, areas=areas, evidence=dataset.evidence,
                  businesses=dataset.businesses, resources=dataset.resources,
                  methodology={"name": "Experimental area vulnerability proxy", "validated_prediction": False,
                               "score_is_probability": False, "configuration": config.model_dump(),
                               "formula": "100 * (burden_weight * B + pressure_weight * P + visual_weight * V * P)",
                               "limitations": ["Selected imagery is not a representative survey.",
                                               "Descriptive pooled ACS changes do not track the same households.",
                                               "Area scores do not establish individual business or tenant distress.",
                                               "Weights and thresholds are provisional; no accuracy claim is made."]})


def write_bundle(bundle: Bundle, output: Path) -> None:
    # Validate again even if the caller mutated a model after construction.
    validated = Bundle.model_validate_json(bundle.model_dump_json())
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(validated.model_dump_json(indent=2) + "\n")
    temporary.replace(output)
