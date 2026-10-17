import type { Area, AssessmentKind, Prediction, PredictionFactor } from '../data/types';

export type Lens = 'outlook' | 'today';

/** Low → high pressure. Paired with text everywhere, so color is never the only signal. */
const STOPS: [number, [number, number, number]][] = [
  [0, [207, 226, 214]], [0.5, [233, 201, 138]], [0.75, [217, 134, 95]], [1, [176, 58, 46]],
];
export const UNRATED_COLOR = '#9aa7aa';

export function rampColor(t: number): string {
  const x = Math.min(1, Math.max(0, t));
  for (let i = 1; i < STOPS.length; i++) {
    const [b, cb] = STOPS[i]!;
    const [a, ca] = STOPS[i - 1]!;
    if (x <= b) {
      const f = (x - a) / (b - a);
      const c = ca.map((v, k) => Math.round(v + f * (cb[k]! - v)));
      return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
    }
  }
  return 'rgb(176, 58, 46)';
}

export function rentPrediction(area: Area): Prediction | undefined {
  return area.predictions?.find((p) => p.key === 'rent_pressure_5yr');
}

export function businessPrediction(area: Area): Prediction | undefined {
  return area.predictions?.find((p) => p.key === 'business_closure_5yr');
}

/** 0–1 value the map colors by, or null when the lens has nothing for this area. */
export function lensValue(area: Area, lens: Lens, kind: AssessmentKind): number | null {
  if (lens === 'outlook') return rentPrediction(area)?.county_percentile ?? null;
  const a = area[kind];
  // Scores cluster between about 20 and 80, so stretch that band for a readable map.
  return a.status === 'rated' && a.score !== null ? (a.score - 20) / 60 : null;
}

export function lensColor(area: Area, lens: Lens, kind: AssessmentKind): string {
  const value = lensValue(area, lens, kind);
  return value === null ? UNRATED_COLOR : rampColor(value);
}

export const TIER_TEXT = { lower: 'Lower', moderate: 'Moderate', higher: 'Higher' } as const;

export function percentileText(p: Prediction): string {
  if (p.county_percentile === null) return '';
  const top = Math.max(1, Math.round((1 - p.county_percentile) * 100));
  return top <= 50 ? `top ${top}% of LA County tracts` : `bottom ${Math.round(p.county_percentile * 100) || 1}% of LA County tracts`;
}

const signed = (fraction: number) => `${fraction >= 0 ? '+' : '−'}${Math.abs(fraction * 100).toFixed(0)}%`;

function formatValue(feature: string, value: number | null): string {
  if (value === null) return 'unknown';
  if (feature === 'log_population') return `${Math.round(Math.exp(value)).toLocaleString('en-US')} people`;
  if (feature === 'median_year_built') return String(Math.round(value));
  if (feature === 'rent_income_pct') return `${value.toFixed(1)}%`;
  if (feature.endsWith('_vs_county')) return `${value.toFixed(2)}× county`;
  if (feature.endsWith('_density')) return `${value.toFixed(1)} per km²`;
  if (feature.endsWith('_prior')) return signed(value);
  // ZIP growth is stored as a log difference.
  if (feature.endsWith('_growth')) return signed(Math.exp(value) - 1);
  return `${(value * 100).toFixed(1)}%`;
}

/** "Median rent relative to county: 0.82× the county median (typical tract: 1.00×)". */
export function factorText(f: PredictionFactor): string {
  const typical = f.county_median === null ? '' : ` · typical tract ${formatValue(f.feature, f.county_median)}`;
  return `${f.label}: ${formatValue(f.feature, f.value)}${typical}`;
}

export function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}
