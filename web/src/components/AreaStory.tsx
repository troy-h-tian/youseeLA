import type { Area, AssessmentKind } from '../data/types';
import { areaChanges } from '../lib/areaStory';

export function AreaStory({ area, kind, onEvidence }: {
  area: Area; kind: AssessmentKind; onEvidence: () => void;
}) {
  const changes = areaChanges(area, kind);
  return <section className="area-story" aria-label="What changed here">
    <p className="city-eyebrow">THE AREA IN A FEW WORDS</p>
    <h3>What changed here?</h3>
    {changes.length ? <>
      {changes.map(change => <p key={change.period + change.text}>{change.text}<small>{change.period}</small></p>)}
      <p className="story-limit">These records describe property activity{kind === 'commercial' ? ' and ZIP-wide business counts' : ''}, not proof of displacement. They do not affect the score.</p>
    </> : <p>There aren’t two comparable periods in the available neighborhood records, so we can’t summarize a change from them. The dated facts below show what is available.</p>}
    <button className="panel-link" onClick={onEvidence}>Check the evidence <span aria-hidden="true">→</span></button>
  </section>;
}
