import type { Business } from '../data/types';
import { rampColor, TIER_TEXT } from '../lib/outlook';

/** One business's support priority: its own model estimate plus its area's rent outlook, with sources. */
export function SupportPriority({ business }: { business: Business }) {
  const outlook = business.outlook;
  if (!outlook) return null;
  return <section className="support-priority" aria-label="Support priority">
    <p className="city-eyebrow">SUPPORT PRIORITY</p>
    <div className="priority-headline">
      <span className="priority-score" style={{ background: rampColor(outlook.priority_score / 100) }}>{Math.round(outlook.priority_score)}</span>
      <div><strong>{TIER_TEXT[outlook.tier]} priority</strong><small>out of 100 · where a visit helps most, not a prediction that this business will close</small></div>
    </div>
    <ul className="priority-reasons">{outlook.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
    <details className="outlook-details"><summary>How is this calculated?</summary>
      <p>{outlook.basis}</p><p>{outlook.accuracy}</p>
      {business.opened_source_url && <p>Opening year: <a href={business.opened_source_url} target="_blank" rel="noopener noreferrer">source</a>{business.opened_note ? ` · ${business.opened_note}` : ''}</p>}
    </details>
  </section>;
}
