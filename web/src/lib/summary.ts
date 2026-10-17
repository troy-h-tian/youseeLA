import type { Area, Bundle, Evidence } from '../data/types';
import { formatDate, formatIndicator, formatPoints, ratingText } from './format';

/**
 * Plain-text housing evidence summary that an organization can paste into
 * notes or an email. Deliberately states what the assessment is not.
 */
export function housingSummary(area: Area, bundle: Bundle): string {
  const a = area.housing;
  const evidence = new Map(bundle.evidence.map((e) => [e.id, e] as const));
  const lines: string[] = [
    `Housing assessment — ${area.label} (tract ${area.id})`,
    `Data: ${bundle.data_kind === 'real' ? 'real pipeline output' : 'DEMO FIXTURE, not real data'}; generated ${bundle.generated_at}; rubric ${a.config_version}`,
    `Rating: ${ratingText(a)}${a.status === 'rated' ? '' : ` — ${a.unrated_reason ?? 'insufficient evidence'}`}`,
    '',
    'Contributions:',
    ...a.contributions.map(
      (c) => `- ${c.label} (${c.formula}): ${formatPoints(c.points)}${c.note ? ` — ${c.note}` : ''}`,
    ),
    '',
    'Indicators:',
    ...area.indicators.map(
      (i) => `- ${i.label}: ${formatIndicator(i)} (${i.source_period})${i.unavailable_reason ? ` — ${i.unavailable_reason}` : ''}`,
    ),
    '',
    `Residential image coverage: ${a.coverage.distinct_locations}/${a.coverage.required_locations} locations, ${a.coverage.assessable_frontages}/${a.coverage.required_frontages} frontages`,
  ];
  if (a.warnings.length > 0) lines.push('', 'Warnings:', ...a.warnings.map((w) => `- ${w}`));
  const sources = a.evidence_ids.map((id) => evidence.get(id)).filter((e): e is Evidence => e !== undefined);
  if (sources.length > 0) {
    lines.push('', 'Sources:', ...sources.map((e) => `- ${e.title} (${formatDate(e.captured_at)}): ${e.source_url}`));
  }
  lines.push(
    '',
    'This is an experimental area-level vulnerability proxy for prioritizing follow-up. It is not an eviction forecast, an aid-eligibility decision, or a statement about any household.',
  );
  return lines.join('\n');
}
