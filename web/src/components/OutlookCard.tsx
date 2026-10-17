import type { Area, Mode } from '../data/types';
import { businessPrediction, factorText, pct, percentileText, rampColor, rentPrediction, TIER_TEXT } from '../lib/outlook';

/** Trained-model outlook for an area: rent pressure for everyone, plus business survival by type in business mode. */
export function OutlookCard({ area, mode }: { area: Area; mode: Mode }) {
  const rent = rentPrediction(area);
  const business = mode === 'business' ? businessPrediction(area) : undefined;
  if (!rent && !business) {
    return <section className="outlook-card" aria-label="Five-year outlook"><h3>Five-year outlook</h3>
      <p className="summary-caption">No model prediction is available for this area.</p></section>;
  }
  return <section className="outlook-card" aria-label="Five-year outlook">
    {rent && <>
      <p className="city-eyebrow">{rent.kind === 'backtest' ? 'MODEL BACKTEST' : 'FIVE-YEAR OUTLOOK'} · {rent.horizon}</p>
      <h3>Will rents outpace incomes?</h3>
      <div className="outlook-headline">
        <span className="outlook-swatch" style={{ background: rampColor(rent.county_percentile ?? 0) }} aria-hidden="true" />
        <div>
          <strong>{rent.tier ? TIER_TEXT[rent.tier] : 'Unrated'} pressure</strong>
          <small>{percentileText(rent)}{rent.probability !== null && ` · ${pct(rent.probability)} model probability of top-quarter rent pressure`}</small>
        </div>
      </div>
      {rent.outcome && <p className="outlook-outcome">{rent.outcome}</p>}
      {rent.factors.length > 0 && <>
        <p className="outlook-subhead">What pushes this area’s outlook up</p>
        <ul className="outlook-factors">{rent.factors.map((f) => <li key={f.feature}>
          <span>{factorText(f)}</span><small>+{Math.round(f.effect * 100)} pts</small>
        </li>)}</ul>
        <p className="summary-caption">Points: how much lower the probability would be if this one value matched the typical LA County tract. These are statistical associations, not causes.</p>
      </>}
      <details className="outlook-details"><summary>How accurate is this?</summary>
        <p>{rent.accuracy}</p><p><strong>Based on:</strong> {rent.basis}</p>
      </details>
    </>}
    {business && <div className="business-outlook">
      <h3>Business staying power</h3>
      <p className="summary-caption">Estimated chance a business of each type closes or moves within five years. A typical business here, not any specific one.</p>
      <table>
        <thead><tr><th scope="col">Type</th><th scope="col">New (1 yr)</th><th scope="col">Typical</th><th scope="col">LA typical</th></tr></thead>
        <tbody>{Object.entries(business.by_type).map(([name, v]) => <tr key={name}>
          <th scope="row">{name}</th><td>{pct(v.new_business ?? 0)}</td><td>{pct(v.typical ?? 0)}</td><td>{pct(v.county_typical ?? 0)}</td>
        </tr>)}</tbody>
      </table>
      <p className="outlook-tip">New businesses are the most fragile. A first visit, a review or a repeat order helps most in their early years.</p>
      <details className="outlook-details"><summary>How accurate is this?</summary>
        <p>{business.accuracy}</p><p><strong>Based on:</strong> {business.basis}</p>
      </details>
    </div>}
  </section>;
}
