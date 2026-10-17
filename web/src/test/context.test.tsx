import { readFileSync } from 'node:fs';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { Explorer } from '../App';
import type { Bundle } from '../data/types';

vi.mock('../components/CityMap', () => ({ CityMap: () => <div /> }));

const select = () => {
 fireEvent.click(screen.getByRole('button', { name: 'Browse all places' }));
 fireEvent.click(screen.getByRole('button', { name: /Dulan.*Manchester/i }));
};
const real = (): Bundle => JSON.parse(readFileSync('public/data/demo.json', 'utf8')) as Bundle;

it('labels rough scores with their Census-only basis and shows the model outlook', () => {
  render(<Explorer bundle={real()} />);
  select();
  const context = screen.getByRole('region', { name: 'Census housing context' });
  expect(within(context).getByText('2020–2024')).toBeVisible();
  expect(within(context).getByText(/rent burden/i)).toBeVisible();
  expect(screen.getByText(/Today’s pressure score: \d+\.\d \/ 100/)).toBeVisible();
  expect(screen.getByText(/Rough score from Census data only/)).toBeVisible();
  const outlook = screen.getByRole('region', { name: 'Five-year outlook' });
  expect(within(outlook).getByText('Will rents outpace incomes?')).toBeVisible();
  expect(within(outlook).getByText(/of LA County tracts/)).toBeVisible();
  expect(within(outlook).getByRole('table')).toHaveTextContent('Food & drink');
  expect(screen.getByText(/not a business rating/)).toBeVisible();
});

it('does not display missing Census values as zero or erase missing model inputs', () => {
  const bundle = real();
  for (const area of bundle.areas) {
    for (const indicator of area.indicators) indicator.value = null;
    // Without Census inputs even the rough score is unavailable.
    for (const kind of ['housing', 'commercial'] as const) {
      Object.assign(area[kind], { status: 'insufficient_evidence', score: null, tier: null, score_range: null, basis: null,
        contributions: [], unrated_reason: 'Rent-burden data is missing or invalid' });
    }
  }
  render(<Explorer bundle={bundle} />);
  select();
  fireEvent.click(screen.getByRole('tab', { name: 'Evidence' }));
  expect(screen.queryByRole('region', { name: 'Census housing context' })).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Unrated: insufficient evidence');
  expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
});
