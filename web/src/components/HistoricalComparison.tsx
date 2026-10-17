import { useState } from 'react';
import comparison from '../data/historical-comparison.json';

type Photo = typeof comparison.pair.old;

function dateLabel(value: string): string {
  return new Date(value + 'T12:00:00Z').toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC',
  });
}

function HistoricalPhoto({ photo, label }: { photo: Photo; label: string }) {
  const [failed, setFailed] = useState(false);
  const src = import.meta.env.BASE_URL + photo.image_url;
  return (
    <figure className="historical-photo">
      <figcaption><span>{label}</span><time dateTime={photo.date}>{dateLabel(photo.date)}</time></figcaption>
      {failed ? <p role="note">{label} image could not be loaded. Open the source below.</p> : (
        <a href={src} target="_blank" rel="noreferrer" aria-label={`Open full ${label.toLowerCase()} photo`}>
          <img src={src} alt={`${label} view of the parking structure and commercial buildings in Inglewood`}
            loading="lazy" onError={() => setFailed(true)} />
        </a>
      )}
      <p className="historical-credit">
        <a href={photo.source_url} target="_blank" rel="noreferrer">{label} Mapillary source</a>
        <br />{photo.attribution} · <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>
      </p>
    </figure>
  );
}

export function HistoricalComparison() {
  const { pair, result, review_notes } = comparison;
  const findings = result.findings;
  return (
    <section className="historical" id="historical-comparison" aria-labelledby="historical-title">
      <div className="historical-heading">
        <div>
          <p className="historical-eyebrow">Historical evidence study · 2019 → 2020</p>
          <h2 id="historical-title">{comparison.title}</h2>
          <p>{comparison.location_label}</p>
        </div>
        <span className="historical-tag">Historical only</span>
      </div>
      <p className="historical-context">Two real photographs, {pair.distance_m} metres between recorded camera positions.
        This comparison does not affect current area scores. No visible change is not evidence of low displacement pressure.</p>
      <div className="historical-photos">
        <HistoricalPhoto photo={pair.old} label="Earlier" />
        <HistoricalPhoto photo={pair.new} label="Later" />
      </div>
      <div className="historical-findings">
        <div>
          <h3>Model observations · awaiting human review</h3>
          <p>The model marked these views <strong>{findings.comparability.replaceAll('_', ' ')}</strong>.
            Read the evidence and limitations alongside each observation.</p>
          <ol className="historical-observations">
            {findings.observations.map((observation, index) => (
              <li key={index}>
                <div className="historical-observation-title"><h4>{observation.location}</h4>
                  <span>{observation.category.replaceAll('_', ' ')}</span></div>
                <dl>
                  <dt>Earlier</dt><dd>{observation.earlier_evidence}</dd>
                  <dt>Later</dt><dd>{observation.later_evidence}</dd>
                </dl>
                <p><strong>Model interpretation:</strong> {observation.interpretation}</p>
              </li>
            ))}
          </ol>
        </div>
        <aside className="historical-limits" aria-label="Comparison limitations">
          <h3>What this establishes</h3>
          <p>A dated, inspectable comparison of visible structures. It is not a business risk rating.</p>
          <h3>Review notes</h3>
          <ul>{review_notes.map((note) => <li key={note}>{note}</li>)}</ul>
          <details>
            <summary>Matching landmarks and model limitations</summary>
            <ul>{findings.matching_landmarks.map((item) => <li key={item}>{item}</li>)}</ul>
            <ul>{findings.limitations.map((item) => <li key={item}>{item}</li>)}</ul>
          </details>
          <p className="historical-credit">Model: {result.model}<br />Generated: {dateLabel(result.generated_at.slice(0, 10))}.
            Original photographs unchanged; model-derived descriptions are provided under CC BY-SA 4.0.</p>
        </aside>
      </div>
    </section>
  );
}
