import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { validateBundle } from '../data/load';
import type { Bundle } from '../data/types';

describe('real pipeline handoff', () => {
  const bundle = JSON.parse(readFileSync('public/data/demo.json', 'utf8')) as Bundle;
  it('accepts the exported real data and preserves missing scores', () => {
    expect(validateBundle(bundle)).toEqual([]);
    expect(bundle.data_kind).toBe('real');
    expect(bundle.businesses.length).toBeGreaterThanOrEqual(5);
    for (const area of bundle.areas) {
      for (const mode of ['housing', 'commercial'] as const) {
        if (area[mode].status === 'insufficient_evidence') {
          expect(area[mode].score).toBeNull();
          expect(area[mode].unrated_reason).toBeTruthy();
        }
      }
    }
  });
  it('keeps available Census context accessible for unrated areas', () => {
    const downtown = bundle.areas.find(area => area.id === '06037601001')!;
    expect(downtown.indicators.find(i => i.key === 'rent_burden_share')?.value).not.toBeNull();
    expect(downtown.commercial.evidence_ids.length).toBeGreaterThan(0);
    expect(bundle.evidence.every(item => item.reviewed)).toBe(true);
  });
});
