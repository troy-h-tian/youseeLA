import type { Area, AssessmentKind, Indicator } from '../data/types';

/** These are direct Census estimates, never substitutes for missing model scores. */
export function contextIndicator(area: Area, key: string): Indicator | undefined {
  return area.indicators.find((item) => item.key === key && item.value !== null);
}

export function useContextView(areas: Area[], kind: AssessmentKind): boolean {
  return areas.length > 0 && areas.every((area) => area[kind].status !== 'rated')
    && areas.some((area) => contextIndicator(area, 'rent_burden_share') !== undefined);
}
