"""Provisional numerical + CLIP fusion, with no human change-label prerequisite."""
from datetime import date
from typing import TYPE_CHECKING

from youseela.contracts import Assessment, ClipPairFeature, Contribution, Coverage, Evidence, Mode, NumericalIndicators, ScoreRange

if TYPE_CHECKING:
    from youseela.scoring import AssessmentConfig


def assess_clip(area_id: str, mode: Mode, indicators: NumericalIndicators, evidence: list[Evidence],
                config: 'AssessmentConfig', as_of: date, pairs: list[ClipPairFeature]) -> Assessment:
    from youseela.scoring import distance_m
    lookup = {e.id:e for e in evidence if e.area_id == area_id and e.source_date <= as_of}
    reasons: list[str] = []
    if indicators.rent_burden_share is None:
        reasons.append('Rent-burden estimate is unavailable')
    if indicators.affordability_pressure is None:
        reasons.append('Compatible Census affordability-change estimates are unavailable')
    if not indicators.evidence_ids or any(ref not in lookup or lookup[ref].kind != 'census' or not lookup[ref].reviewed for ref in indicators.evidence_ids):
        reasons.append('Matching Census sources are required')
    accepted: list[ClipPairFeature] = []
    locations: list[Evidence] = []
    for candidate in sorted(pairs, key=lambda p:p.id):
        if candidate.area_id != area_id or candidate.mode != mode:
            continue
        pair = ClipPairFeature.model_validate(candidate.model_dump())
        old, new = lookup.get(pair.earlier_image_id), lookup.get(pair.later_image_id)
        if old is None or new is None:
            continue
        if any(e.kind != 'image' or e.mode != mode or e.site_id != pair.site_id for e in (old, new)):
            continue
        if old.source_date >= new.source_date or (as_of-new.source_date).days > config.maximum_image_age_days:
            continue
        if distance_m(old, new) > config.maximum_pair_distance_m:
            continue
        if any(e.site_id == new.site_id or distance_m(e, new) < config.minimum_site_distance_m for e in locations):
            continue
        accepted.append(pair)
        locations.append(new)
    if len(accepted) < config.minimum_pairs:
        reasons.append(f'Need {config.minimum_pairs} distinct dated {mode} CLIP image pair(s)')
    refs = sorted({ref for p in accepted for ref in [p.earlier_image_id, p.later_image_id]})
    dates = [lookup[ref].source_date for ref in refs]
    coverage = Coverage(images=len(refs), sites=len(accepted), frontages=0,
                        earliest_capture=min(dates, default=None), latest_capture=max(dates, default=None))
    warnings = [*indicators.warnings,
                'Experimental CLIP + Census index; untrained fusion weights, not a validated prediction or probability.',
                'Visual difference can reflect viewpoint, lighting, vegetation or vehicles; it does not establish redevelopment or its direction.',
                f'{len(accepted)} sampled image pair(s); not a representative survey. No human change labels were used.',
                'Zero-visual ablation holds numerical weights fixed; the separate numerical-only baseline renormalizes them.']
    common = dict(mode=mode, coverage=coverage, warnings=warnings, configuration_version=config.version)
    if reasons:
        return Assessment(status='insufficient_evidence', reasons=reasons, **common)
    weights = getattr(config, mode)
    visual = sum(p.visual_difference for p in accepted)/len(accepted)
    burden, pressure = float(indicators.rent_burden_share), float(indicators.affordability_pressure)
    features = [
        ('rent_burden','Housing affordability exposure',burden,weights.burden,indicators.evidence_ids,'Share of renter households with computable ratios spending at least 30% of income on rent.'),
        ('affordability_change','Affordability-change proxy',pressure,weights.pressure,indicators.evidence_ids,'Rent growth relative to income growth across compatible ACS periods.'),
        ('clip_visual_difference','CLIP visual difference',visual,weights.visual_interaction,refs,'Mean (1 − cosine similarity)/2 across distinct dated image pairs. An appearance difference, not proof of gentrification.')]
    contributions = [Contribution(feature=key,label=label,value=value,weight=weight,points=100*weight*value,evidence_ids=ids,explanation=note)
                     for key,label,value,weight,ids,note in features]
    score = round(sum(c.points for c in contributions),6)
    bounds = indicators.affordability_pressure_range
    score_range = None
    if bounds:
        score_range = ScoreRange(lower=round(100*(weights.burden*burden+weights.pressure*bounds.lower+weights.visual_interaction*visual),6),
                                 upper=round(100*(weights.burden*burden+weights.pressure*bounds.upper+weights.visual_interaction*visual),6))
    return Assessment(status='rated', score=score, score_range=score_range,
                      tier='lower' if score < 33 else 'moderate' if score < 67 else 'higher',
                      contributions=contributions, evidence_ids=sorted(set(refs+indicators.evidence_ids)), **common)
