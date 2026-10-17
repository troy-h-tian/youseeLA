import { useState } from 'react';
import type { Area, Bundle } from '../../data/types';
import { formatDate, formatIndicator, formatPoints, ratingText } from '../../lib/format';
import { housingSummary } from '../../lib/summary';
import { applicableResources, ResourceList } from '../../components/ResourceList';

interface Props {
  bundle: Bundle;
  area: Area;
  compareId: string | null;
  onCompareChange: (id: string | null) => void;
}

export function HousingPanel({ bundle, area, compareId, onCompareChange }: Props) {
  const others = bundle.areas.filter((a) => a.id !== area.id);
  const compare = others.find((a) => a.id === compareId) ?? null;
  const resources = applicableResources(bundle.resources, 'housing', area.id);

  return (
    <>
      <section className="card" aria-labelledby="compare-title">
        <h2 id="compare-title">Compare housing factors</h2>
        {others.length === 0 ? (
          <p className="empty">Only one area is available, so there is nothing to compare.</p>
        ) : (
          <>
            <label className="field">
              <span>Compare {area.label} with</span>
              <select value={compare?.id ?? ''} onChange={(e) => onCompareChange(e.target.value || null)}>
                <option value="">Choose an area…</option>
                {others.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.label} (tract {a.id})
                  </option>
                ))}
              </select>
            </label>
            {compare && <ComparisonTable left={area} right={compare} />}
          </>
        )}
      </section>

      <section className="card" aria-labelledby="resources-title">
        <h2 id="resources-title">Tenant resources for {area.label}</h2>
        {resources.length === 0 ? (
          <p className="empty">No verified tenant resource is listed for this area.</p>
        ) : (
          <ResourceList resources={resources} />
        )}
        <p className="muted">Check each organization&rsquo;s current service area and eligibility directly.</p>
      </section>

      <EvidenceSummary area={area} bundle={bundle} />
    </>
  );
}

function ComparisonTable({ left, right }: { left: Area; right: Area }) {
  const features = [...new Set([...left.housing.contributions, ...right.housing.contributions].map((c) => c.feature))];
  const term = (area: Area, feature: string) => area.housing.contributions.find((c) => c.feature === feature);
  const indicatorKeys = [...new Set([...left.indicators, ...right.indicators].map((i) => i.key))];
  const indicator = (area: Area, key: string) => area.indicators.find((i) => i.key === key);
  const dates = (area: Area) => {
    const range = area.housing.coverage.capture_date_range;
    return range ? `${formatDate(range[0])} – ${formatDate(range[1])}` : 'No images';
  };

  return (
    <div className="table-wrap">
      <table className="compare">
        <caption className="visually-hidden">
          Housing factors for {left.label} and {right.label}
        </caption>
        <thead>
          <tr>
            <th scope="col">Factor</th>
            <th scope="col">{left.label}</th>
            <th scope="col">{right.label}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row">Housing rating</th>
            <td>{ratingText(left.housing)}</td>
            <td>{ratingText(right.housing)}</td>
          </tr>
          {features.map((f) => {
            const l = term(left, f);
            const r = term(right, f);
            return (
              <tr key={f}>
                <th scope="row">{(l ?? r)?.label}</th>
                <td>{l ? formatPoints(l.points) : '—'}</td>
                <td>{r ? formatPoints(r.points) : '—'}</td>
              </tr>
            );
          })}
          {indicatorKeys.map((key) => {
            const l = indicator(left, key);
            const r = indicator(right, key);
            return (
              <tr key={key}>
                <th scope="row">{(l ?? r)?.label}</th>
                <td>{l ? `${formatIndicator(l)} (${l.source_period})` : '—'}</td>
                <td>{r ? `${formatIndicator(r)} (${r.source_period})` : '—'}</td>
              </tr>
            );
          })}
          <tr>
            <th scope="row">Residential locations</th>
            <td>
              {left.housing.coverage.distinct_locations}/{left.housing.coverage.required_locations}
            </td>
            <td>
              {right.housing.coverage.distinct_locations}/{right.housing.coverage.required_locations}
            </td>
          </tr>
          <tr>
            <th scope="row">Residential frontages</th>
            <td>
              {left.housing.coverage.assessable_frontages}/{left.housing.coverage.required_frontages}
            </td>
            <td>
              {right.housing.coverage.assessable_frontages}/{right.housing.coverage.required_frontages}
            </td>
          </tr>
          <tr>
            <th scope="row">Image capture dates</th>
            <td>{dates(left)}</td>
            <td>{dates(right)}</td>
          </tr>
          <tr>
            <th scope="row">Linked evidence items</th>
            <td>{left.housing.evidence_ids.length}</td>
            <td>{right.housing.evidence_ids.length}</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function EvidenceSummary({ area, bundle }: { area: Area; bundle: Bundle }) {
  const [copied, setCopied] = useState<'idle' | 'copied' | 'failed'>('idle');
  const text = housingSummary(area, bundle);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied('copied');
    } catch {
      setCopied('failed');
    }
  };

  return (
    <section className="card" aria-labelledby="summary-title">
      <h2 id="summary-title">Evidence summary for follow-up</h2>
      <p className="muted">
        Plain-text summary of this area&rsquo;s housing assessment and sources. It is not an aid-eligibility decision.
      </p>
      <p>
        <button type="button" className="button" onClick={copy}>
          Copy summary
        </button>{' '}
        <span role="status" className="muted">
          {copied === 'copied' ? 'Copied to clipboard.' : copied === 'failed' ? 'Copy failed — select the text below instead.' : ''}
        </span>
      </p>
      <details open={copied === 'failed'}>
        <summary>Show summary text</summary>
        <textarea className="summary-text" readOnly value={text} rows={12} aria-label="Evidence summary text" />
      </details>
    </section>
  );
}
