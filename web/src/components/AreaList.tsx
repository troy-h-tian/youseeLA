import type { Area, AssessmentKind } from '../data/types';
import { rankAreas } from '../lib/ranking';
import { RatingBadge } from './RatingBadge';

interface Props {
  areas: Area[];
  kind: AssessmentKind;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function AreaList({ areas, kind, selectedId, onSelect }: Props) {
  const { rated, unrated, orderingSupported } = rankAreas(areas, kind);
  const item = (area: Area, showReason: boolean) => (
    <li key={area.id}>
      <button
        type="button"
        className="area-item"
        aria-pressed={area.id === selectedId}
        onClick={() => onSelect(area.id)}
      >
        <span className="area-item__label">{area.label}</span>
        <span className="area-item__id">Tract {area.id}</span>
        <RatingBadge assessment={area[kind]} />
        {showReason && area[kind].unrated_reason && (
          <span className="area-item__reason">{area[kind].unrated_reason}</span>
        )}
      </button>
    </li>
  );

  return (
    <nav className="area-list" aria-label={`Areas by ${kind} assessment`}>
      <h2 className="section-title">{orderingSupported ? 'Rated areas' : 'Assessed areas — not ranked'} ({rated.length})</h2>
      {!orderingSupported && <p className="muted">Sensitivity ranges overlap. Areas are listed alphabetically, not by support priority.</p>}
      {rated.length === 0 ? (
        <p className="muted">No area has enough evidence for a {kind} rating.</p>
      ) : (
        orderingSupported ? <ol className="area-list__items">{rated.map((a) => item(a, false))}</ol>
          : <ul className="area-list__items">{rated.map((a) => item(a, false))}</ul>
      )}
      {unrated.length > 0 && (
        <>
          <h2 className="section-title">Unrated — insufficient evidence ({unrated.length})</h2>
          <ul className="area-list__items">{unrated.map((a) => item(a, true))}</ul>
        </>
      )}
    </nav>
  );
}
