"""An auditable heuristic, explicitly not a validated displacement prediction."""

import json
import math
from datetime import date
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from youseela.contracts import ClipPairFeature, Assessment, Contribution, Coverage, Evidence, Mode, NumericalIndicators, Record, ScoreRange, UnitValue


class Weights(Record):
    burden: UnitValue
    pressure: UnitValue
    visual_interaction: UnitValue

    @model_validator(mode="after")
    def sum_to_one(self) -> "Weights":
        if abs(self.burden + self.pressure + self.visual_interaction - 1) > 1e-9:
            raise ValueError("Weights must sum to one")
        return self


class AssessmentConfig(Record):
    version: str = "experimental-v2-sensitivity"
    visual_method: Literal["reviewed_frontages", "clip_pairs"] = "reviewed_frontages"
    minimum_pairs: int = Field(default=1, ge=1)
    maximum_pair_distance_m: float = Field(default=25, gt=0)
    minimum_sites: int = Field(default=3, ge=1)
    minimum_frontages: int = Field(default=5, ge=1)
    maximum_image_age_days: int = Field(default=1095, ge=1)
    minimum_site_distance_m: float = Field(default=25, gt=0)
    housing: Weights = Field(default_factory=lambda: Weights(burden=.6, pressure=.25, visual_interaction=.15))
    commercial: Weights = Field(default_factory=lambda: Weights(burden=.3, pressure=.5, visual_interaction=.2))


def load_config(path: Path | None = None) -> AssessmentConfig:
    return AssessmentConfig.model_validate_json(path.read_text()) if path else AssessmentConfig()


def distance_m(a: Evidence, b: Evidence) -> float:
    if a.latitude is None or a.longitude is None or b.latitude is None or b.longitude is None:
        return 0
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat = lat2-lat1
    dlon = math.radians(b.longitude-a.longitude)
    return 6371000 * 2 * math.asin(min(1, math.sqrt(math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2)))


def assess(area_id: str, mode: Mode, indicators: NumericalIndicators,
           evidence: list[Evidence], config: AssessmentConfig, as_of: date,
           clip_pairs: list[ClipPairFeature] | None = None) -> Assessment:
    if config.visual_method == "clip_pairs":
        from youseela.clip_scoring import assess_clip
        return assess_clip(area_id, mode, indicators, evidence, config, as_of, clip_pairs or [])
    reasons: list[str] = []
    lookup = {e.id: e for e in evidence if e.reviewed and e.area_id == area_id and e.source_date <= as_of}
    if indicators.rent_burden_share is None:
        reasons.append("Rent-burden data is missing or invalid")
    if indicators.affordability_pressure is None:
        reasons.append("Compatible, interpretable affordability-change evidence is missing")
    if not indicators.evidence_ids or any(ref not in lookup or lookup[ref].kind != "census" for ref in indicators.evidence_ids):
        reasons.append("Numerical evidence needs reviewed, matching Census sources")
    historical_ids = {
        ref for e in lookup.values() if e.kind == "image" and e.mode == mode
        for observation in e.observations if observation.redevelopment == "present"
        for ref in observation.corroboration_ids
        if ref in lookup and lookup[ref].kind == "image" and lookup[ref].mode == mode
        and lookup[ref].site_id == e.site_id and lookup[ref].source_date < e.source_date
    }
    images = sorted((e for e in lookup.values() if e.kind == "image" and e.mode == mode and e.id not in historical_ids
                     and 0 <= (as_of-e.source_date).days <= config.maximum_image_age_days), key=lambda e: e.id)
    sites: list[Evidence] = []
    frontages: dict[str, bool] = {}
    used_ids: set[str] = set(indicators.evidence_ids)
    ambiguous = False
    for item in images:
        contributes_new_frontage = False
        used_ids.add(item.id)
        for observation in item.observations:
            active = observation.redevelopment == "present"
            if observation.redevelopment == "unclear":
                ambiguous = True
                continue
            if active:
                confirmations = [lookup.get(ref) for ref in observation.corroboration_ids]
                if not confirmations or any(c is None or c.mode not in {mode, "both"} or c.id == item.id
                                            or c.kind not in {"project", "image"}
                                            or (c.kind == "project" and
                                                ((c.site_id is not None and c.site_id != item.site_id)
                                                 or (c.site_id is None and item.site_id not in c.applies_to_site_ids)))
                                            or (c.kind == "image" and (c.source_date >= item.source_date or c.site_id != item.site_id))
                                            for c in confirmations):
                    ambiguous = True
                    continue
                used_ids.update(observation.corroboration_ids)
            if observation.frontage_id in frontages and frontages[observation.frontage_id] != active:
                ambiguous = True
            if observation.frontage_id not in frontages:
                contributes_new_frontage = True
            frontages[observation.frontage_id] = active
        if contributes_new_frontage and all(item.site_id != old.site_id and distance_m(item, old) >= config.minimum_site_distance_m for old in sites):
            sites.append(item)
    coverage = Coverage(images=len(images), sites=len(sites), frontages=len(frontages),
                        redevelopment_frontages=sum(frontages.values()),
                        earliest_capture=min((e.source_date for e in images), default=None),
                        latest_capture=max((e.source_date for e in images), default=None))
    if len(sites) < config.minimum_sites:
        reasons.append(f"Need {config.minimum_sites} distinct reviewed {mode} image sites")
    if len(frontages) < config.minimum_frontages:
        reasons.append(f"Need {config.minimum_frontages} uniquely identifiable, assessable frontages")
    if ambiguous:
        reasons.append("Visual activity is ambiguous, inconsistent, or lacks independent corroboration")
    warnings = list(indicators.warnings) + [
        "Experimental vulnerability proxy; not a probability or proof of gentrification.",
        "Small selected image sample is not a representative neighborhood survey.",
        "Redevelopment may improve affordability; feature weights are unvalidated assumptions."]
    if mode == "commercial":
        warnings.append("Housing indicators describe area context, not commercial rents or individual business finances.")
    common = dict(mode=mode, configuration_version=config.version, coverage=coverage, warnings=warnings)
    if reasons:
        return Assessment(status="insufficient_evidence", reasons=reasons, **common)
    burden = float(indicators.rent_burden_share)
    pressure = float(indicators.affordability_pressure)
    visual = sum(frontages.values()) / len(frontages)
    weights = getattr(config, mode)
    features = [
        ("rent_burden", "Existing housing affordability exposure", burden, weights.burden, indicators.evidence_ids,
         "Share of rent-paying households spending at least 30% of income on rent; not evidence of gentrification alone."),
        ("affordability_change", "Descriptive affordability-change proxy", pressure, weights.pressure, indicators.evidence_ids,
         "Rent change relative to household-income change in compatible pooled Census estimates."),
        ("corroborated_visual_change", "Physical change with affordability context", visual*pressure, weights.visual_interaction,
         sorted(used_ids), f"{sum(frontages.values())}/{len(frontages)} sampled frontages show corroborated redevelopment; multiplied by affordability pressure.")]
    contributions = [Contribution(feature=key, label=label, value=value, weight=weight,
                                  points=100*weight*value, evidence_ids=refs, explanation=explanation)
                     for key, label, value, weight, refs, explanation in features]
    score = round(sum(c.points for c in contributions), 6)
    score_range = None
    if indicators.affordability_pressure_range:
        bounds = indicators.affordability_pressure_range
        def sensitivity(p: float) -> float:
            return round(100 * (weights.burden * burden + (weights.pressure + weights.visual_interaction * visual) * p), 6)
        score_range = ScoreRange(lower=sensitivity(bounds.lower), upper=sensitivity(bounds.upper))
        warnings.append("Provisional point estimate. Sensitivity ranges omit uncertainty in rent burden, image sampling, and chosen weights; they are not confidence intervals.")
    return Assessment(status="rated", score=score, tier="lower" if score < 33 else "moderate" if score < 67 else "higher",
                      score_range=score_range,
                      contributions=contributions, evidence_ids=sorted(used_ids), **common)
