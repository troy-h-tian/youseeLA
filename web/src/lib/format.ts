import type { Assessment, Business, Indicator, Tier } from '../data/types';

export const TIER_LABEL: Record<Tier, string> = {
  lower: 'Lower',
  moderate: 'Moderate',
  higher: 'Higher',
};

/** Short text used wherever a rating appears, so color is never the only signal. */
export function ratingText(assessment: Assessment): string {
  if (assessment.status !== 'rated' || assessment.score === null || assessment.tier === null) {
    return 'Unrated';
  }
  return `${TIER_LABEL[assessment.tier]} · ${formatScore(assessment.score)}/100`;
}

export function formatScore(score: number): string {
  return score.toFixed(1);
}

export function formatPoints(points: number | null): string {
  return points === null ? 'Unavailable' : `${points.toFixed(1)} pts`;
}

export function formatTermValue(value: number | null): string {
  return value === null ? 'Unavailable' : value.toFixed(3);
}

const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
const count = new Intl.NumberFormat('en-US');

export function formatIndicator(indicator: Pick<Indicator, 'value' | 'unit'>): string {
  const { value, unit } = indicator;
  if (value === null) return 'Unavailable';
  switch (unit) {
    case 'share':
      return `${(value * 100).toFixed(1)}%`;
    case 'usd':
      return usd.format(value);
    case 'count':
      return count.format(value);
    case 'ratio':
      return value.toFixed(3);
  }
}

export function formatMoe(indicator: Pick<Indicator, 'margin_of_error' | 'unit'>): string | null {
  if (indicator.margin_of_error === null) return null;
  return `± ${formatIndicator({ value: indicator.margin_of_error, unit: indicator.unit })}`;
}

export function formatDate(iso: string): string {
  // Date-only strings are calendar dates; parse as UTC so they do not shift a day.
  const date = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T00:00:00Z`) : new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' });
}

export function directionsUrl(business: Business): string {
  if (business.directions_url) return business.directions_url;
  const { lat, lon } = business.location;
  return `https://www.openstreetmap.org/directions?to=${lat}%2C${lon}`;
}
