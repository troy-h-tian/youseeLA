import { readFileSync } from 'node:fs';
import { render, screen, within } from '@testing-library/react';
import { expect, it } from 'vitest';
import { Explorer } from '../App';
import type { Bundle } from '../data/types';

const real = (): Bundle => JSON.parse(readFileSync('public/data/demo.json', 'utf8')) as Bundle;

it('leads with measured Census context when every combined score is unavailable', () => {
  render(<Explorer bundle={real()} />);
  expect(screen.getByRole('heading', { name: 'Available neighborhood data' })).toBeVisible();
  const context = screen.getByRole('region', { name: 'Census housing context' });
  expect(within(context).getByText('2020–2024')).toBeVisible();
  expect(within(context).getByText(/rent burden/i)).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Explore areas (30)' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'Rated areas (0)' })).not.toBeInTheDocument();
  expect(screen.queryByRole('table', { name: 'Score contributions' })).not.toBeInTheDocument();
  expect(screen.getByText(/Map shows rent burden, not a risk score/)).toBeVisible();
});

it('does not display missing Census values as zero or erase missing model inputs', () => {
  const bundle = real();
  for (const area of bundle.areas) for (const indicator of area.indicators) indicator.value = null;
  render(<Explorer bundle={bundle} />);
  expect(screen.queryByRole('region', { name: 'Census housing context' })).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Unrated: insufficient evidence');
  expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
});
