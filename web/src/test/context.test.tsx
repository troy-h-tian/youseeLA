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

it('leads with measured Census context when every combined score is unavailable', () => {
  render(<Explorer bundle={real()} />);
  select();
  const context = screen.getByRole('region', { name: 'Census housing context' });
  expect(within(context).getByText('2020–2024')).toBeVisible();
  expect(within(context).getByText(/rent burden/i)).toBeVisible();
  expect(screen.getByText('Combined assessment pending')).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'Rated areas (0)' })).not.toBeInTheDocument();
  expect(screen.queryByRole('table', { name: 'Score contributions' })).not.toBeInTheDocument();
  expect(screen.getByText(/not a business rating/)).toBeVisible();
});

it('does not display missing Census values as zero or erase missing model inputs', () => {
  const bundle = real();
  for (const area of bundle.areas) for (const indicator of area.indicators) indicator.value = null;
  render(<Explorer bundle={bundle} />);
  select();
  fireEvent.click(screen.getByRole('tab', { name: 'Evidence' }));
  expect(screen.queryByRole('region', { name: 'Census housing context' })).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('Unrated: insufficient evidence');
  expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
});
