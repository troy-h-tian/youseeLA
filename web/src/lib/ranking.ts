import type { Area, AssessmentKind } from '../data/types';

export interface RankedAreas {
  rated: Area[];
  unrated: Area[];
  orderingSupported: boolean;
}

/**
 * Rated areas sort by score (highest first) with a stable label/id tie-break.
 * Unrated areas are listed separately so they never read as low scores.
 */
export function rankAreas(areas: Area[], kind: AssessmentKind): RankedAreas {
  const byName = (a: Area, b: Area) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id);
  const rated: Area[] = [];
  const unrated: Area[] = [];
  for (const area of areas) {
    const assessment = area[kind];
    if (assessment.status === 'rated' && assessment.score !== null) rated.push(area);
    else unrated.push(area);
  }
  rated.sort((a, b) => (b[kind].score as number) - (a[kind].score as number) || byName(a, b));
  const orderingSupported = !rated.some((a, index) => rated.slice(index + 1).some(b => {
    if (!a[kind].score_range && !b[kind].score_range) return false;
    const left = a[kind].score_range ?? { lower: a[kind].score!, upper: a[kind].score! };
    const right = b[kind].score_range ?? { lower: b[kind].score!, upper: b[kind].score! };
    return Math.max(left.lower, right.lower) <= Math.min(left.upper, right.upper);
  }));
  if (!orderingSupported) rated.sort(byName);
  unrated.sort(byName);
  return { rated, unrated, orderingSupported };
}
