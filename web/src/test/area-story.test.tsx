import { readFileSync } from 'node:fs';
import { render, screen, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import type { Bundle } from '../data/types';
import { areaChanges } from '../lib/areaStory';
import { NextSteps } from '../components/NextSteps';

const real = (): Bundle => JSON.parse(readFileSync('public/data/demo.json', 'utf8'));

it('describes recorded increases and decreases with both source periods', () => {
  const area = real().areas[0]!;
  area.indicators.find(i => i.key === 'built_or_renovated_share_prior')!.value = 0.1;
  area.indicators.find(i => i.key === 'built_or_renovated_share_latest')!.value = 0.2;
  area.indicators.find(i => i.key === 'amenity_establishments_prior')!.value = 12;
  area.indicators.find(i => i.key === 'amenity_establishments_latest')!.value = 8;
  const changes = areaChanges(area, 'commercial');
  expect(changes[0]!.text).toContain('rose from 10.0% to 20.0%');
  expect(changes[0]!.period).toContain('2016–2020');
  expect(changes[0]!.period).toContain('2021–2025');
  expect(changes[1]!.text).toContain('fell from 12 to 8');
});

it('does not invent change from missing values, overlapping periods, or different ZIP areas', () => {
  const area = real().areas[0]!;
  area.indicators.find(i => i.key === 'built_or_renovated_share_latest')!.value = null;
  area.indicators.find(i => i.key === 'amenity_establishments_latest')!.label = 'Counts in a different ZIP';
  expect(areaChanges(area, 'commercial')).toEqual([]);
  area.indicators.find(i => i.key === 'reassessed_share_latest')!.source_period = '2019–2023';
  expect(areaChanges(area, 'housing')).toEqual([]);
});

it('does not turn rounding noise into a claim of change', () => {
  const area = real().areas[0]!;
  area.indicators.find(i => i.key === 'built_or_renovated_share_prior')!.value = 0.10001;
  area.indicators.find(i => i.key === 'built_or_renovated_share_latest')!.value = 0.10002;
  expect(areaChanges(area, 'housing')[0]!.text).toContain('about 10.0% in both periods');
});

it('only offers housing resources that serve the selected area', () => {
  const bundle = real();
  const area = bundle.areas[0]!;
  bundle.resources[0]!.area_ids = ['another-area'];
  render(<NextSteps bundle={bundle} area={area} mode="housing" onBusiness={() => {}} onSupport={() => {}} />);
  const actions = screen.getByRole('region', { name: 'What you can do' });
  expect(within(actions).queryByRole('link', { name: new RegExp(bundle.resources[0]!.name) })).not.toBeInTheDocument();
  expect(within(actions).getByRole('link', { name: new RegExp(bundle.resources[1]!.name) })).toHaveAttribute('href', bundle.resources[1]!.url);
});

it('keeps present-day actions out of the historical view', () => {
  const bundle = real();
  bundle.methodology.visual_method = 'clip_pairs';
  render(<NextSteps bundle={bundle} area={bundle.areas[0]!} mode="housing" onBusiness={() => {}} onSupport={() => {}} />);
  expect(screen.getByRole('link', { name: 'Explore today' })).toHaveAttribute('href', '?data=demo');
  expect(screen.queryByText(bundle.resources[0]!.name)).not.toBeInTheDocument();
});
