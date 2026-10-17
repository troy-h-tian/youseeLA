import { fireEvent, render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { HistoricalComparison } from '../components/HistoricalComparison';

it('shows both real capture dates, raw observations and review limitations', () => {
  render(<HistoricalComparison />);
  expect(screen.getByRole('heading', { name: 'One commercial street, two dates' })).toBeVisible();
  expect(screen.getByText('May 20, 2019')).toBeVisible();
  expect(screen.getByText('January 9, 2020')).toBeVisible();
  expect(screen.getByText(/does not establish tree growth/)).toBeVisible();
  expect(screen.getByText(/does not affect current area scores/)).toBeVisible();
  expect(screen.getAllByRole('img')).toHaveLength(2);
  expect(screen.getAllByRole('link', { name: /Mapillary source/ })).toHaveLength(2);
});

it('keeps attribution and observations available when a photo fails', () => {
  render(<HistoricalComparison />);
  fireEvent.error(screen.getAllByRole('img')[0]!);
  expect(screen.getByText(/Earlier image could not be loaded/)).toBeVisible();
  expect(screen.getByRole('link', { name: 'Earlier Mapillary source' })).toBeVisible();
  expect(screen.getByText('left side of street')).toBeVisible();
});
