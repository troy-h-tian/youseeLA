import { readFileSync } from 'node:fs';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { Explorer } from '../App';
import type { Bundle } from '../data/types';

vi.mock('../components/CityMap', () => ({ CityMap: () => <div aria-label="Interactive city map" /> }));
const real = (): Bundle => JSON.parse(readFileSync('public/data/demo.json', 'utf8'));

it('searches a real business, opens its location and preserves source-backed details', async () => {
  const user = userEvent.setup();
  render(<Explorer bundle={real()} />);
  await user.type(screen.getByRole('searchbox'), 'Dulan');
  await user.click(screen.getByRole('button', { name: /Dulan.*Manchester/i }));
  const panel = screen.getByRole('region', { name: 'Location details' });
  expect(within(panel).getByRole('heading', { name: "Dulan's Soul Food Kitchen" })).toBeVisible();
  expect(within(panel).getByRole('link', { name: 'Visit website' })).toHaveAttribute('href', 'https://www.dulans-sfk.com/');
  expect(within(panel).getByText('58.7%')).toBeVisible();
  await user.click(screen.getByRole('button', { name: 'Close location details' }));
  expect(screen.queryByRole('region', { name: 'Location details' })).not.toBeInTheDocument();
});

it('offers an honest empty search state and keeps experimental data labeling visible', async () => {
  const user = userEvent.setup();
  const bundle = real();
  bundle.data_kind = 'fixture';
  render(<Explorer bundle={bundle} />);
  expect(screen.getByText(/Synthetic demo/)).toBeVisible();
  await user.type(screen.getByRole('searchbox'), 'zzzz-no-match');
  expect(screen.getByText(/No matching places/)).toBeVisible();
});
