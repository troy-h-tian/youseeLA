"""Translate validated pipeline records into the explorer's display contract."""

from typing import Any

from youseela.contracts import Area, Assessment, Bundle
from youseela.scoring import AssessmentConfig


def web_assessment(assessment: Assessment, area: Area, config: AssessmentConfig) -> dict[str, Any]:
    coverage = assessment.coverage
    dates = ([coverage.earliest_capture.isoformat(), coverage.latest_capture.isoformat()]
             if coverage.earliest_capture and coverage.latest_capture else None)
    # Unrated areas still expose the available Census context in their drawer.
    refs = sorted(set(assessment.evidence_ids + area.indicators.evidence_ids))
    return {
        'status': assessment.status, 'score': assessment.score, 'tier': assessment.tier,
        'score_range': assessment.score_range.model_dump() if assessment.score_range else None,
        'unrated_reason': '; '.join(assessment.reasons) or None,
        'warnings': assessment.warnings, 'evidence_ids': refs,
        'config_version': assessment.configuration_version,
        'contributions': [dict(feature=c.feature, label=c.label, weight=c.weight,
                               value=c.value, points=c.points,
                               formula=f'100 × {c.weight:g} × {c.feature}',
                               numerator=None, denominator=None, evidence_ids=c.evidence_ids,
                               note=c.explanation) for c in assessment.contributions],
        'coverage': dict(distinct_locations=coverage.sites, assessable_frontages=coverage.frontages,
                         required_locations=config.minimum_sites, required_frontages=config.minimum_frontages,
                         capture_date_range=dates),
    }


def to_web_bundle(bundle: Bundle) -> dict[str, Any]:
    """Adapt names and display fields without changing any assessment result."""
    bundle = Bundle.model_validate_json(bundle.model_dump_json())
    config = AssessmentConfig.model_validate(bundle.methodology['configuration'])
    areas = []
    for area in bundle.areas:
        indicators = []
        for key, label in [('rent_burden_share', 'Households spending at least 30% of income on rent'),
                           ('renter_share', 'Renter share of occupied households'),
                           ('affordability_pressure', 'Descriptive affordability-change proxy')]:
            value = getattr(area.indicators, key)
            indicators.append(dict(key=key, label=label, value=value,
                                   unit='ratio' if key == 'affordability_pressure' else 'share',
                                   source_period=(' versus '.join(area.indicators.periods) if key == 'affordability_pressure'
                                                  else (area.indicators.periods[-1] if area.indicators.periods else 'Unspecified')),
                                   margin_of_error=None, numerator=None, denominator=None,
                                   evidence_ids=area.indicators.evidence_ids,
                                   unavailable_reason='; '.join(area.indicators.warnings) if value is None else None))
        areas.append(dict(id=area.id, label=area.name, boundary=area.geometry,
                          boundary_note=f"Full tract, including portions outside Inglewood where applicable. Boundary: {area.boundary_vintage or 'unspecified'}. Assessed as of {bundle.assessed_as_of.isoformat()}.",
                          indicators=indicators,
                          housing=web_assessment(area.housing, area, config),
                          commercial=web_assessment(area.commercial, area, config)))
    formulas = {}
    for mode in ['housing', 'commercial']:
        w = getattr(config, mode)
        formulas[mode] = f'100 × ({w.burden:g} × B + {w.pressure:g} × P + {w.visual_interaction:g} × V × P)'
    return dict(
        schema_version=1, generated_at=bundle.generated_at.isoformat(), data_kind=bundle.data_kind,
        methodology=dict(config_version=config.version,
                         summary='Experimental area support-priority proxy, not a validated prediction. B is rent burden, P is affordability pressure, and V is corroborated visual change. Missing evidence remains unrated.',
                         limitations=bundle.methodology['limitations'],
                         tier_bands=dict(lower_below=33, moderate_below=67), formulas=formulas),
        areas=areas,
        businesses=[dict(id=b.id, name=b.name, address=b.address,
                         location=dict(lat=b.latitude, lon=b.longitude), area_id=b.area_id,
                         category='Local business', description=b.description, rationale=b.recommendation_reason,
                         source_url=b.source_url, verified_at=b.verified_at.isoformat(),
                         website_url=b.website_url, directions_url=b.directions_url) for b in bundle.businesses],
        resources=[dict(id=r.id, name=r.name, kind='housing', description=r.description,
                        url=r.source_url, service_area=r.jurisdiction, area_ids=None,
                        source_url=r.source_url, verified_at=r.verified_at.isoformat()) for r in bundle.resources],
        evidence=[dict(id=e.id, evidence_type='project_record' if e.kind == 'project' else e.kind,
                       area_id=e.area_id, title=f'{e.kind.title()} evidence · {e.area_id} · {e.source_date.isoformat()}',
                       source_url=e.source_url, attribution=e.attribution, license=e.license,
                       captured_at=e.source_date.isoformat(),
                       location=dict(lat=e.latitude, lon=e.longitude) if e.latitude is not None else None,
                       frontage_class='residential' if e.mode == 'housing' else 'commercial' if e.mode == 'commercial' else None,
                       image_url=None, reviewed=e.reviewed,
                       observations=[dict(feature=o.frontage_id, label='Visible physical work', status=o.redevelopment,
                                          visible_count=None, description=o.description) for o in e.observations],
                       corrections=[e.note] if e.note else []) for e in bundle.evidence],
    )
