import type { Area, AssessmentKind } from '../data/types';
import { formatIndicator } from './format';

export interface AreaChange {
  text: string;
  period: string;
}

/** Describe recorded differences only; these indicators do not establish displacement or its cause. */
export function areaChanges(area: Area, kind: AssessmentKind): AreaChange[] {
  const definitions = [
    { key: 'built_or_renovated_share', subject: 'The share of taxable parcels recorded as built or renovated' },
    ...(kind === 'commercial'
      ? [{ key: 'amenity_establishments', subject: 'The ZIP-wide count of cafes, restaurants, bars and groceries' }]
      : [{ key: 'reassessed_share', subject: 'The share of taxable parcels reassessed after a sale or new construction' }]),
  ];
  return definitions.flatMap(({ key, subject }) => {
    const before = area.indicators.find(i => i.key === `${key}_prior`);
    const after = area.indicators.find(i => i.key === `${key}_latest`);
    if (!before || !after || before.value === null || after.value === null
      || before.unit !== after.unit || before.label !== after.label) return [];
    const earlierYears = before.source_period.match(/\d{4}/g)?.map(Number) ?? [];
    const laterYears = after.source_period.match(/\d{4}/g)?.map(Number) ?? [];
    if (!earlierYears.length || !laterYears.length || Math.max(...earlierYears) >= Math.min(...laterYears)) return [];
    const from = formatIndicator(before);
    const to = formatIndicator(after);
    const text = from === to
      ? `${subject} was about ${to} in both periods.`
      : `${subject} ${after.value > before.value ? 'rose' : 'fell'} from ${from} to ${to}.`;
    return [{ text, period: `${before.source_period} → ${after.source_period}` }];
  });
}
