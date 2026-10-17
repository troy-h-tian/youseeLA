import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { App, Explorer } from '../App';
import { validateBundle } from '../data/load';
import type { Area, Bundle } from '../data/types';
import { rankAreas } from '../lib/ranking';
import { housingSummary } from '../lib/summary';

const fixtureText = readFileSync(resolve(__dirname, '../../public/data/fixture.json'), 'utf8');
const fixture = (): Bundle => JSON.parse(fixtureText) as Bundle;

const areaButton = (label: string) => screen.getByRole('button', { name: new RegExp(`^${label}`) });

function renderExplorer(bundle = fixture()) {
  const user = userEvent.setup();
  render(<Explorer bundle={bundle} />);
  return user;
}

describe('bundle contract guard', () => {
  it('accepts the acceptance fixture', () => {
    expect(validateBundle(fixture())).toEqual([]);
  });

  it('rejects an unrated assessment that carries a numeric score', () => {
    const bundle = fixture();
    const c = bundle.areas.find((a) => a.id === 'fixture-c')!;
    c.housing.score = 0;
    expect(validateBundle(bundle)).toContainEqual(expect.stringContaining('insufficient evidence but a non-null score'));
  });

  it('rejects a rated assessment without a bounded score and tier', () => {
    const bundle = fixture();
    const a = bundle.areas.find((x) => x.id === 'fixture-a')!;
    a.commercial.score = 104;
    a.housing.tier = null;
    const problems = validateBundle(bundle);
    expect(problems).toContainEqual(expect.stringContaining('not within 0–100'));
    expect(problems).toContainEqual(expect.stringContaining('rated but has no tier'));
  });

  it('rejects dangling evidence and area references', () => {
    const bundle = fixture();
    bundle.areas[0]!.housing.evidence_ids.push('no-such-evidence');
    bundle.businesses[0]!.area_id = 'no-such-area';
    const problems = validateBundle(bundle);
    expect(problems).toContainEqual(expect.stringContaining('references missing evidence no-such-evidence'));
    expect(problems).toContainEqual(expect.stringContaining('references unknown area no-such-area'));
  });

  it('fixture contributions sum to each rated score', () => {
    for (const area of fixture().areas) {
      for (const a of [area.housing, area.commercial]) {
        if (a.status !== 'rated') continue;
        const sum = a.contributions.reduce((s, c) => s + (c.points ?? 0), 0);
        expect(sum).toBeCloseTo(a.score!, 1);
      }
    }
  });
});

describe('area ranking', () => {
  it('sorts rated areas by mode score with a stable tie-break and keeps unrated separate', () => {
    const bundle = fixture();
    const [a, b, , d] = bundle.areas as [Area, Area, Area, Area];
    // Force a tie between D and B in commercial mode; label decides.
    d.commercial.score = b.commercial.score;
    const ranked = rankAreas(bundle.areas, 'commercial');
    expect(ranked.rated.map((x) => x.id)).toEqual([a.id, b.id, d.id]);
    expect(ranked.unrated.map((x) => x.id)).toEqual(['fixture-c']);

    const housing = rankAreas(bundle.areas, 'housing');
    expect(housing.rated.map((x) => x.id)).toEqual(['fixture-a', 'fixture-d']);
    expect(housing.unrated.map((x) => x.id)).toEqual(['fixture-b', 'fixture-c']);
  });
});

describe('explorer', () => {
  it('shows a persistent fixture label', () => {
    renderExplorer();
    expect(screen.getByRole('note')).toHaveTextContent(/Demo fixture/);
  });

  it('switching modes keeps the selected area but changes the assessment and actions', async () => {
    const user = renderExplorer();
    await user.click(areaButton('Fixture Area B'));
    expect(screen.getByRole('heading', { name: 'Commercial area vulnerability' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Local businesses in Fixture Area B/ })).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /Housing support/ }));
    expect(screen.getByRole('tab', { name: /Housing support/ })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('heading', { name: 'Housing area vulnerability' })).toBeInTheDocument();
    expect(screen.getByText('Fixture Area B · Tract fixture-b')).toBeInTheDocument();
    // Area B has commercial evidence but too little residential imagery.
    expect(screen.getByText(/Residential imagery covers 1 of 3 required locations/, { selector: '.unrated p' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: /Local businesses/ })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Tenant resources for Fixture Area B/ })).toBeInTheDocument();
  });

  it('supports arrow-key navigation between modes', async () => {
    const user = renderExplorer();
    screen.getByRole('tab', { name: /Support businesses/ }).focus();
    await user.keyboard('{ArrowRight}');
    expect(screen.getByRole('tab', { name: /Housing support/ })).toHaveFocus();
    expect(screen.getByRole('tab', { name: /Housing support/ })).toHaveAttribute('aria-selected', 'true');
  });

  it('displays an unrated area with its reason and never as a zero score', async () => {
    const user = renderExplorer();
    await user.click(areaButton('Fixture Area C'));
    const panel = screen.getByRole('heading', { name: 'Commercial area vulnerability' }).closest('section')!;
    expect(within(panel).getByRole('status')).toHaveTextContent(/Unrated: insufficient evidence/);
    expect(within(panel).getByRole('status')).toHaveTextContent(/P is unavailable/);
    expect(within(panel).queryByText(/Exploratory score/)).not.toBeInTheDocument();
    expect(within(panel).queryByText(/0\.0 pts/)).not.toBeInTheDocument();
    expect(within(panel).getAllByText('Unavailable').length).toBeGreaterThan(0);
  });

  it('lists unrated areas separately from rated ones', () => {
    renderExplorer();
    const unratedHeading = screen.getByRole('heading', { name: /Unrated — insufficient evidence \(1\)/ });
    const list = unratedHeading.nextElementSibling as HTMLElement;
    expect(within(list).getByRole('button', { name: /Fixture Area C/ })).toBeInTheDocument();
  });

  it('labels business cards with area context rather than a business rating', async () => {
    const user = renderExplorer();
    await user.click(areaButton('Fixture Area A'));
    const card = screen.getByRole('listitem', { name: 'Fixture Bakery' });
    expect(card).toHaveTextContent(/Area context, not a business rating/);
    expect(card).toHaveTextContent(/Fixture Area A commercial vulnerability Higher · 68\.4\/100/);
    expect(within(card).getByRole('link', { name: /Visit website/ })).toHaveAttribute('href', 'https://example.com/fixture-business-1');
    expect(within(card).getByRole('link', { name: /Directions/ })).toHaveAttribute('href', expect.stringContaining('openstreetmap.org/directions'));
    expect(card).not.toHaveTextContent(/★|stars?\b|out of 5/i);
  });

  it('filters evidence to the active mode', async () => {
    const user = renderExplorer();
    await user.click(areaButton('Fixture Area A'));
    await user.click(screen.getByRole('button', { name: /View commercial evidence/ }));
    let dialog = screen.getByRole('dialog', { name: 'Commercial evidence' });
    expect(within(dialog).getAllByText(/Fixture commercial frontage/).length).toBe(5);
    expect(within(dialog).queryByText(/Fixture residential frontage/)).not.toBeInTheDocument();

    await user.click(within(dialog).getByRole('button', { name: /^Image/ }));
    expect(within(dialog).queryByText(/Fixture ACS tables/)).not.toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: /Housing support/ }));
    await user.click(screen.getByRole('button', { name: /View housing evidence/ }));
    dialog = screen.getByRole('dialog', { name: 'Housing evidence' });
    expect(within(dialog).getAllByText(/Fixture residential frontage/).length).toBe(5);
    expect(within(dialog).queryByText(/Fixture commercial frontage/)).not.toBeInTheDocument();
  });

  it('keeps textual evidence when an image fails to load', async () => {
    const user = renderExplorer();
    await user.click(screen.getByRole('tab', { name: /Housing support/ }));
    await user.click(areaButton('Fixture Area A'));
    await user.click(screen.getByRole('button', { name: /View housing evidence/ }));
    const item = document.querySelector('[data-evidence-id="fixture-a-res-5"]') as HTMLElement;
    fireEvent.error(within(item).getByRole('img'));
    expect(within(item).getByRole('note')).toHaveTextContent(/could not be loaded.*do not confirm current conditions/);
    expect(within(item).getByText(/No construction or reconstruction visible/)).toBeInTheDocument();
  });

  it('compares two areas side by side in housing mode', async () => {
    const user = renderExplorer();
    await user.click(screen.getByRole('tab', { name: /Housing support/ }));
    await user.click(areaButton('Fixture Area A'));
    await user.selectOptions(screen.getByLabelText(/Compare Fixture Area A with/), 'fixture-b');
    const table = screen.getByRole('table', { name: /Housing factors for Fixture Area A and Fixture Area B/ });
    const ratingRow = within(table).getByRole('row', { name: /Housing rating/ });
    expect(ratingRow).toHaveTextContent('Higher · 67.5/100');
    expect(ratingRow).toHaveTextContent('Unrated');
  });

  it('only shows tenant resources that serve the selected area', async () => {
    const user = renderExplorer();
    await user.click(screen.getByRole('tab', { name: /Housing support/ }));
    await user.click(areaButton('Fixture Area A'));
    expect(screen.getByRole('link', { name: 'Fixture Rental Assistance Desk' })).toBeInTheDocument();
    await user.click(areaButton('Fixture Area D'));
    expect(screen.queryByRole('link', { name: 'Fixture Rental Assistance Desk' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Fixture Tenant Rights Clinic' })).toBeInTheDocument();
  });
});

describe('housing evidence summary', () => {
  it('states the fixture status, missing values and that it is not an eligibility decision', () => {
    const bundle = fixture();
    const text = housingSummary(bundle.areas.find((a) => a.id === 'fixture-c')!, bundle);
    expect(text).toMatch(/DEMO FIXTURE/);
    expect(text).toMatch(/Rating: Unrated — No compatible earlier ACS vintage/);
    expect(text).toMatch(/Median rent change.*Unavailable/);
    expect(text).toMatch(/not .*an aid-eligibility decision/);
  });
});

describe('loading states', () => {
  const respond = (body: unknown, status = 200) =>
    (async () => new Response(JSON.stringify(body), { status })) as unknown as typeof fetch;

  it('shows a contract error with specific problems', async () => {
    const bundle = fixture();
    bundle.areas[2]!.housing.score = 12;
    render(<App source="demo" fetchImpl={respond(bundle)} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/does not match the data contract/);
    expect(screen.getByRole('alert')).toHaveTextContent(/fixture-c housing has insufficient evidence but a non-null score/);
    expect(screen.getByRole('link', { name: /labeled demo fixture/ })).toHaveAttribute('href', '?data=fixture');
  });

  it('shows an HTTP error when the real bundle has not been generated', async () => {
    render(<App source="demo" fetchImpl={respond({}, 404)} />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/data\/demo\.json returned HTTP 404/);
  });

  it('shows an empty state for a bundle with no areas', async () => {
    render(<App source="fixture" fetchImpl={respond({ ...fixture(), areas: [], businesses: [], evidence: [], resources: [] })} />);
    expect(await screen.findByText(/contains no areas yet/)).toBeInTheDocument();
  });
});
