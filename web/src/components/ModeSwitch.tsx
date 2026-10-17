import { useRef } from 'react';
import type { KeyboardEvent } from 'react';
import type { Mode } from '../data/types';

const MODES: { id: Mode; label: string; audience: string }[] = [
  { id: 'business', label: 'Support businesses', audience: 'For customers' },
  { id: 'housing', label: 'Housing support', audience: 'For organizations' },
];

interface Props {
  mode: Mode;
  onChange: (mode: Mode) => void;
  panelId: string;
}

/** Two equally weighted tabs; arrow keys move between them per the ARIA tabs pattern. */
export function ModeSwitch({ mode, onChange, panelId }: Props) {
  const refs = useRef<Record<Mode, HTMLButtonElement | null>>({ business: null, housing: null });

  const onKeyDown = (event: KeyboardEvent) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const index = MODES.findIndex((m) => m.id === mode);
    const next =
      event.key === 'Home' ? 0 : event.key === 'End' ? MODES.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + MODES.length) % MODES.length;
    const target = MODES[next];
    if (!target) return;
    onChange(target.id);
    refs.current[target.id]?.focus();
  };

  return (
    <div className="mode-switch" role="tablist" aria-label="Explorer mode" onKeyDown={onKeyDown}>
      {MODES.map((m) => (
        <button
          key={m.id}
          ref={(el) => {
            refs.current[m.id] = el;
          }}
          id={`tab-${m.id}`}
          type="button"
          role="tab"
          aria-selected={mode === m.id}
          aria-controls={panelId}
          tabIndex={mode === m.id ? 0 : -1}
          className="mode-tab"
          onClick={() => onChange(m.id)}
        >
          <span className="mode-tab__label">{m.label}</span>
          <span className="mode-tab__audience">{m.audience}</span>
        </button>
      ))}
    </div>
  );
}
