import { readFileSync } from 'node:fs';
import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import type { Bundle } from '../data/types';
import { NeighborhoodSummary } from '../components/NeighborhoodSummary';

it('keeps a missing latest observation missing rather than substituting an older value', () => {
  const bundle: Bundle = JSON.parse(readFileSync('public/data/demo.json', 'utf8'));
  const area = bundle.areas[0]!;
  const indicator = area.indicators.find(i => i.key === 'reassessed_share_latest')!;
  indicator.value = null;
  indicator.unavailable_reason = 'Too few taxable parcels.';
  render(<NeighborhoodSummary area={area} kind="housing" onSources={() => {}} />);
  expect(screen.getByText('Unavailable')).toBeVisible();
  expect(screen.getByText('Too few taxable parcels.')).toBeVisible();
  expect(screen.queryByText(/ZIP/)).not.toBeInTheDocument();
});

it('omits the summary if the dataset provides no additional context', () => {
  const bundle: Bundle = JSON.parse(readFileSync('public/data/demo.json', 'utf8'));
  const area = { ...bundle.areas[0]!, indicators: [], reference_typology: null };
  render(<NeighborhoodSummary area={area} kind="commercial" onSources={() => {}} />);
  expect(screen.queryByRole('region', { name: 'Neighborhood indicators' })).not.toBeInTheDocument();
});
