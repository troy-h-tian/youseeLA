import type { Area, AssessmentKind, Methodology } from '../data/types';
import { formatDate, formatIndicator, formatMoe, formatPoints, formatScore, formatTermValue, TIER_LABEL } from '../lib/format';
import { NumericalContext } from './NumericalContext';
import { contextIndicator } from '../lib/context';
import { RatingBadge } from './RatingBadge';

const HEADINGS: Record<AssessmentKind, { title: string; context: string; frontage: string }> = {
  commercial: {
    title: 'Commercial area vulnerability',
    context:
      'Area context for the surrounding Census tract. It is not a rating of, or a prediction about, any individual business.',
    frontage: 'commercial',
  },
  housing: {
    title: 'Housing area vulnerability',
    context:
      'Area-level context for prioritizing follow-up. It is not an eviction forecast or a statement about any household.',
    frontage: 'residential',
  },
};

interface Props {
  area: Area;
  kind: AssessmentKind;
  methodology: Methodology;
  onOpenEvidence: () => void;
}

export function AssessmentPanel({ area, kind, methodology, onOpenEvidence }: Props) {
  const a = area[kind];
  const text = HEADINGS[kind];
  const rated = a.status === 'rated' && a.score !== null;
  const hasContext = !!contextIndicator(area, 'rent_burden_share') || !!contextIndicator(area, 'renter_share');

  return (
    <section className="card assessment" aria-labelledby={`assessment-${kind}-title`}>
      <header className="assessment__header">
        <div>
          <p className="eyebrow">{area.label} · Tract {area.id}</p>
          <h2 id={`assessment-${kind}-title`}>{text.title}</h2>
        </div>
        {!rated && hasContext ? <span className="context-badge">Census data available</span> : <RatingBadge assessment={a} />}
      </header>
      <p className="context-label">
        <strong>Experimental area context.</strong> {text.context}
      </p>

      <NumericalContext area={area} />

      {rated && a.score_range ? (
        <div className="context-label">
          <p>Provisional point estimate <strong>{formatScore(a.score!)} / 100</strong>.</p>
          <p>Sensitivity range <strong>{formatScore(a.score_range.lower)}–{formatScore(a.score_range.upper)}</strong>.</p>
          <p>{a.score_range.explanation}</p>
        </div>
      ) : rated ? (
        <p className="score-line">
          Exploratory score <strong>{formatScore(a.score as number)}</strong> out of 100 —{' '}
          <strong>{TIER_LABEL[a.tier!]}</strong> tier under this rubric (below {methodology.tier_bands.lower_below} lower,
          below {methodology.tier_bands.moderate_below} moderate). Not a probability.
        </p>
      ) : hasContext ? (
        <details className="model-status">
          <summary>Combined assessment pending — view missing inputs</summary>
          <p>{a.unrated_reason}</p>
          <p>Available Census measurements are shown above. The missing inputs listed here prevent a combined score.</p>
        </details>
      ) : (
        <div className="unrated" role="status">
          <p><strong>Unrated: insufficient evidence.</strong> {a.unrated_reason}</p>
          <p className="muted">Missing evidence is not treated as low vulnerability.</p>
        </div>
      )}

      {a.warnings.length > 0 && (
        <details className="model-status"><summary>Method and data limitations</summary>
        <ul className="warnings" aria-label="Warnings">
          {a.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul></details>
      )}

      {rated && <>
      {methodology.visual_method === 'clip_pairs' && <p className="context-label">
        With the visual input set to zero and numerical inputs held fixed, this score would be{' '}
        <strong>{formatScore(a.contributions.filter(c => c.feature !== 'clip_visual_difference').reduce((sum, c) => sum + (c.points ?? 0), 0))}</strong>.
        CLIP contributes <strong>{(a.contributions.find(c => c.feature === 'clip_visual_difference')?.points ?? 0).toFixed(2)}</strong> points.
        This is an input ablation, not an accuracy measurement.
      </p>}
      <h3>How the score is built</h3>
      <p className="formula">
        <code>{methodology.formulas[kind]}</code>
      </p>
      <div className="table-wrap">
        <table className="contributions">
          <caption className="visually-hidden">Score contributions</caption>
          <thead>
            <tr>
              <th scope="col">Term</th>
              <th scope="col">Value</th>
              <th scope="col">Weight</th>
              <th scope="col">Points</th>
            </tr>
          </thead>
          <tbody>
            {a.contributions.map((c) => (
              <tr key={c.feature}>
                <th scope="row">
                  {c.label}
                  <span className="term-formula">{c.formula}</span>
                  {c.numerator !== null && c.denominator !== null && (
                    <span className="term-raw">
                      {c.numerator.toLocaleString('en-US')} / {c.denominator.toLocaleString('en-US')}
                    </span>
                  )}
                  {c.note && <span className="term-note">{c.note}</span>}
                </th>
                <td>{formatTermValue(c.value)}</td>
                <td>{c.weight.toFixed(2)}</td>
                <td>{formatPoints(c.points)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      </>}

      <details className="model-status"><summary>Image coverage ({text.frontage})</summary>
      <dl className="facts">
        <div>
          <dt>{methodology.visual_method === 'clip_pairs' ? 'Distinct dated image pairs' : 'Distinct reviewed locations'}</dt>
          <dd>
            {a.coverage.distinct_locations} of {a.coverage.required_locations} required
          </dd>
        </div>
        <div>
          <dt>{methodology.visual_method === 'clip_pairs' ? 'Frontage counts (not used by CLIP)' : 'Assessable frontages'}</dt>
          <dd>
            {a.coverage.assessable_frontages} of {a.coverage.required_frontages} required
          </dd>
        </div>
        <div>
          <dt>Capture dates</dt>
          <dd>
            {a.coverage.capture_date_range
              ? `${formatDate(a.coverage.capture_date_range[0])} – ${formatDate(a.coverage.capture_date_range[1])}`
              : 'No images'}
          </dd>
        </div>
      </dl>

      </details>
      <details className="indicators">
        <summary>Census indicators ({area.indicators.length})</summary>
        <dl className="facts">
          {area.indicators.map((i) => (
            <div key={i.key}>
              <dt>
                {i.label} <span className="muted">({i.source_period})</span>
              </dt>
              <dd>
                {formatIndicator(i)} {formatMoe(i) && <span className="muted">{formatMoe(i)}</span>}
                {i.unavailable_reason && <span className="term-note">{i.unavailable_reason}</span>}
              </dd>
            </div>
          ))}
        </dl>
        {area.boundary_note && <p className="muted">{area.boundary_note}</p>}
      </details>

      <p className="assessment__footer">
        <button type="button" className="button" onClick={onOpenEvidence}>
          View {kind} evidence ({a.evidence_ids.length})
        </button>
        <span className="muted">Rubric {a.config_version}</span>
      </p>
    </section>
  );
}
