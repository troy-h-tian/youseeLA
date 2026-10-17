import { useEffect, useMemo, useRef, useState } from 'react';
import type { Area, AssessmentKind, Evidence, EvidenceType, ObservationStatus } from '../data/types';
import { formatDate } from '../lib/format';

const TYPE_LABEL: Record<EvidenceType, string> = {
  image: 'Image',
  census: 'Census data',
  project_record: 'Project record',
  business_listing: 'Business listing',
  assessor_roll: 'Assessor roll',
  business_patterns: 'ZIP business patterns',
  reference_typology: 'Displacement typology',
};

const STATUS_LABEL: Record<ObservationStatus, string> = {
  present: 'Present',
  absent: 'Absent',
  unclear: 'Unclear',
};

interface Props {
  open: boolean;
  onClose: () => void;
  area: Area;
  kind: AssessmentKind;
  evidence: Evidence[];
}

/** Evidence referenced by the given assessment, in the order the pipeline listed it. */
export function evidenceFor(area: Area, kind: AssessmentKind, evidence: Evidence[]): Evidence[] {
  const byId = new Map(evidence.map((e) => [e.id, e] as const));
  return area[kind].evidence_ids.map((id) => byId.get(id)).filter((e): e is Evidence => e !== undefined);
}

export function EvidenceDrawer({ open, onClose, area, kind, evidence }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  const [filter, setFilter] = useState<EvidenceType | 'all'>('all');
  const items = useMemo(() => evidenceFor(area, kind, evidence), [area, kind, evidence]);
  const types = useMemo(() => [...new Set(items.map((e) => e.evidence_type))], [items]);
  const shown = filter === 'all' ? items : items.filter((e) => e.evidence_type === filter);

  useEffect(() => {
    setFilter('all');
  }, [area.id, kind]);

  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement as HTMLElement | null;
    panelRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeRef.current();
      if (event.key === 'Tab' && panelRef.current) {
        // Keep focus inside the modal drawer.
        const focusable = panelRef.current.querySelectorAll<HTMLElement>('a[href], button, select, [tabindex="0"]');
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!first || !last) return;
        if (event.shiftKey && (document.activeElement === first || document.activeElement === panelRef.current)) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      opener?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <div
        ref={panelRef}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="drawer-title"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer__header">
          <div>
            <p className="eyebrow">{area.label} · Tract {area.id}</p>
            <h2 id="drawer-title">{kind === 'housing' ? 'Housing' : 'Commercial'} evidence</h2>
          </div>
          <button type="button" className="button button--quiet" onClick={onClose}>
            Close
          </button>
        </header>

        {types.length > 1 && (
          <div className="chips" role="group" aria-label="Filter evidence by type">
            <button type="button" className="chip" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
              All ({items.length})
            </button>
            {types.map((t) => (
              <button key={t} type="button" className="chip" aria-pressed={filter === t} onClick={() => setFilter(t)}>
                {TYPE_LABEL[t]} ({items.filter((e) => e.evidence_type === t).length})
              </button>
            ))}
          </div>
        )}

        {shown.length === 0 ? (
          <p className="muted">No evidence is linked to this assessment.</p>
        ) : (
          <ul className="evidence-list">
            {shown.map((item) => (
              <EvidenceItem key={item.id} item={item} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function EvidenceItem({ item }: { item: Evidence }) {
  const [imageFailed, setImageFailed] = useState(false);
  const isImage = item.evidence_type === 'image';

  return (
    <li className="evidence" data-evidence-id={item.id}>
      <h3>{item.title}</h3>
      <p className="evidence__meta">
        <span>{TYPE_LABEL[item.evidence_type]}</span>
        {item.frontage_class && <span>{item.frontage_class === 'residential' ? 'Residential' : 'Commercial'} frontage</span>}
        <span>
          {isImage ? 'Captured' : 'Source date'} {formatDate(item.captured_at)}
        </span>
        <span className={item.reviewed ? 'reviewed' : 'unreviewed'}>{item.reviewed ? 'Human-reviewed' : 'Not reviewed'}</span>
      </p>

      {item.image_url &&
        (imageFailed ? (
          <p className="image-failed" role="note">
            Image could not be loaded. The recorded observations below still apply to the capture date shown; they do
            not confirm current conditions.
          </p>
        ) : (
          <img
            className="evidence__image"
            src={item.image_url}
            alt={`${item.title}, captured ${formatDate(item.captured_at)}`}
            loading="lazy"
            onError={() => setImageFailed(true)}
          />
        ))}

      {item.observations.length > 0 && (
        <ul className="observations" aria-label="Observations">
          {item.observations.map((o) => (
            <li key={o.feature}>
              <span className={`obs obs--${o.status}`}>{STATUS_LABEL[o.status]}</span> <strong>{o.label}</strong>
              {o.visible_count !== null && o.visible_count > 0 && <span className="muted"> · {o.visible_count} visible</span>}
              <span className="obs__desc">{o.description}</span>
            </li>
          ))}
        </ul>
      )}

      {item.corrections.length > 0 && (
        <div className="corrections">
          <strong>Review corrections</strong>
          <ul>
            {item.corrections.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="evidence__source">
        {item.attribution} · {item.license} ·{' '}
        <a href={item.source_url} target="_blank" rel="noopener noreferrer">
          Source
        </a>
      </p>
    </li>
  );
}
