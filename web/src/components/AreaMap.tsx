import { useMemo } from 'react';
import type { Area, AssessmentKind } from '../data/types';
import { fitProjection, labelPoint, pathData } from '../lib/geo';
import { contextIndicator, useContextView } from '../lib/context';
import { TIER_LABEL } from '../lib/format';

const WIDTH = 480;
/** Above this many areas, per-area text labels would overlap and are skipped. */
const MAX_LABELS = 40;

interface Props {
  areas: Area[];
  kind: AssessmentKind;
  selectedId: string | null;
  compareId?: string | null;
  onSelect: (id: string) => void;
}

/**
 * Local SVG geography with no tile basemap. The map is a pointer shortcut;
 * the area list is the keyboard and screen-reader route to the same selection.
 */
export function AreaMap({ areas, kind, selectedId, compareId, onSelect }: Props) {
  const contextView = useContextView(areas, kind);
  const shapes = useMemo(() => {
    const projection = fitProjection(
      areas.map((a) => a.boundary),
      WIDTH,
    );
    return {
      height: projection.height,
      items: areas.map((area) => ({
        id: area.id,
        label: area.label,
        d: pathData(area.boundary, projection),
        at: labelPoint(area.boundary, projection),
      })),
    };
  }, [areas]);
  const byId = useMemo(() => new Map(areas.map((a) => [a.id, a] as const)), [areas]);

  return (
    <figure className="area-map">
      <svg viewBox={`0 0 ${WIDTH} ${shapes.height.toFixed(0)}`} aria-hidden="true" focusable="false">
        <defs>
          <pattern id="hatch-unrated" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" className="map-hatch-bg" />
            <line x1="0" y1="0" x2="0" y2="6" className="map-hatch-line" />
          </pattern>
        </defs>
        {shapes.items.map((shape) => {
          const area = byId.get(shape.id)!;
          const burden = contextIndicator(area, 'rent_burden_share')?.value;
          const assessment = area[kind];
          const tier = assessment?.status === 'rated' && !assessment.score_range ? assessment.tier : null;
          const classes = ['map-area', `map-area--${tier ?? 'unrated'}`];
          if (shape.id === selectedId) classes.push('is-selected');
          if (shape.id === compareId) classes.push('is-compared');
          return (
            <path key={shape.id} d={shape.d} className={classes.join(' ')} style={contextView && burden != null ? { fill: `hsl(205 45% ${94 - burden * 30}%)` } : undefined} onClick={() => onSelect(shape.id)}>
              <title>{shape.label}</title>
            </path>
          );
        })}
        {shapes.items.length <= MAX_LABELS &&
          shapes.items.map((shape) => {
            const assessment = byId.get(shape.id)?.[kind];
            const burden = contextIndicator(byId.get(shape.id)!, 'rent_burden_share')?.value;
            const text = contextView ? (burden == null ? '—' : `${Math.round(burden * 100)}%`) : assessment?.score_range ? 'Provisional' : assessment?.status === 'rated' && assessment.tier ? TIER_LABEL[assessment.tier] : 'Unrated';
            return (
              <text key={shape.id} x={shape.at[0]} y={shape.at[1]} className="map-label" textAnchor="middle">
                {text}
              </text>
            );
          })}
      </svg>
      <figcaption className="map-legend">
        {contextView ? <>
          <strong>Map shows rent burden, not a risk score.</strong>
          <span className="burden-scale" aria-hidden="true" /><span>0% → 100% · darker means a larger share</span>
        </> : <>
        <span><i className="swatch swatch--lower" /> Lower</span>
        <span><i className="swatch swatch--moderate" /> Moderate</span>
        <span><i className="swatch swatch--higher" /> Higher</span>
        <span><i className="swatch swatch--unrated" /> Unrated / provisional</span>
        </>}
        <span className="muted">Census tract boundaries. Tracts may extend beyond Inglewood city limits.</span>
      </figcaption>
    </figure>
  );
}
