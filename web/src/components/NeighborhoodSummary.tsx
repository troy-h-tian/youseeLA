import type { Area, AssessmentKind } from '../data/types';
import { formatIndicator } from '../lib/format';

const PROPERTY_INDICATORS = [
  { key: 'reassessed_share', label: 'Properties reassessed', detail: 'After a sale or new construction · taxable parcels' },
  { key: 'built_or_renovated_share', label: 'Built or renovated', detail: 'Taxable parcels · Assessor estimate' },
];

export function NeighborhoodSummary({ area, kind, onSources }: {
  area: Area; kind: AssessmentKind; onSources: () => void;
}) {
  const definitions = kind === 'commercial'
    ? [...PROPERTY_INDICATORS, { key: 'amenity_establishments', label: 'Neighborhood businesses', detail: 'ZIP-wide count, not openings or closures' }]
    : PROPERTY_INDICATORS;
  const items = definitions.flatMap(definition => {
    // Historical bundles may contain only the earlier observation. Never invent a newer value.
    const indicator = area.indicators.find(i => i.key === `${definition.key}_latest`)
      ?? area.indicators.find(i => i.key === `${definition.key}_prior`);
    return indicator ? [{ ...definition, indicator }] : [];
  });
  if (!items.length && !area.reference_typology) return null;

  return <section className="neighborhood-summary" aria-label="Neighborhood indicators">
    <h3>A little more about this area</h3>
    <p className="summary-caption">Context only · these indicators do not affect the score.</p>
    <dl>{items.map(({ key, label, detail, indicator }) => <div key={key}>
      <dt>{label}<small>{key === 'amenity_establishments' ? indicator.label : detail}</small></dt>
      <dd>{formatIndicator(indicator)}<small>{indicator.source_period}</small>
        {key === 'amenity_establishments' && <small>{detail}</small>}
        {indicator.value === null && <small>{indicator.unavailable_reason ?? 'No value available for this period.'}</small>}
      </dd>
    </div>)}</dl>
    {area.reference_typology && <div className="reference-summary">
      <span>Historical reference · Urban Displacement Project</span>
      <strong>{area.reference_typology.label}</strong>
      <small>{area.reference_typology.source_period} · not a current classification</small>
    </div>}
    <button className="panel-link" onClick={onSources}>View indicator sources <span aria-hidden="true">→</span></button>
  </section>;
}
