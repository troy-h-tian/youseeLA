import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

// Deterministic regressions against the labeled fixture. The real-data flow
// still needs a manual pass once the pipeline exports demo.json.
const FIXTURE = '?data=fixture';

const areaButton = (page: Page, label: string) =>
  page.getByRole('navigation').getByRole('button', { name: new RegExp(`^${label}`) });

test.beforeEach(async ({ page }) => {
  await page.goto(FIXTURE);
  await expect(page.getByRole('note').first()).toContainText('Demo fixture');
});

test('customer journey: area → commercial score → evidence → business → support action', async ({ page }) => {
  await areaButton(page, 'Fixture Area A').click();
  const assessment = page.locator('section.assessment');
  await expect(assessment.getByRole('heading', { name: 'Commercial area vulnerability' })).toBeVisible();
  await expect(assessment).toContainText('Exploratory score 68.4 out of 100');

  await assessment.getByRole('button', { name: /View commercial evidence/ }).click();
  const drawer = page.getByRole('dialog', { name: 'Commercial evidence' });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByText('Human-reviewed').first()).toBeVisible();
  await drawer.getByRole('button', { name: 'Close' }).click();
  await expect(drawer).toBeHidden();

  const card = page.getByRole('listitem', { name: 'Fixture Bakery' });
  await expect(card).toContainText('Area context, not a business rating');
  const website = card.getByRole('link', { name: /Visit website/ });
  await expect(website).toHaveAttribute('href', 'https://example.com/fixture-business-1');
  await expect(website).toHaveAttribute('target', '_blank');
  await expect(website).toHaveAttribute('rel', /noopener/);
});

test('organization journey: same area → housing score → compare → residential evidence → resource', async ({ page }) => {
  await areaButton(page, 'Fixture Area A').click();
  await page.getByRole('tab', { name: /Housing support/ }).click();

  const assessment = page.locator('section.assessment');
  await expect(assessment).toContainText('Fixture Area A · Tract fixture-a');
  await expect(assessment).toContainText('Exploratory score 67.5 out of 100');

  await page.getByLabel(/Compare Fixture Area A with/).selectOption('fixture-d');
  const table = page.getByRole('table', { name: /Housing factors for Fixture Area A and Fixture Area D/ });
  await expect(table.getByRole('row', { name: /Housing rating/ })).toContainText('Lower · 18.6/100');

  await assessment.getByRole('button', { name: /View housing evidence/ }).click();
  const drawer = page.getByRole('dialog', { name: 'Housing evidence' });
  await expect(drawer.getByText('Residential frontage').first()).toBeVisible();
  await expect(drawer.getByText('Commercial frontage')).toHaveCount(0);
  await page.keyboard.press('Escape');

  const resource = page.getByRole('link', { name: 'Fixture Tenant Rights Clinic' });
  await expect(resource).toHaveAttribute('href', 'https://example.org/fixture-tenant-clinic');
});

test('missing evidence stays unrated in both modes and a failed image keeps its text', async ({ page }) => {
  await areaButton(page, 'Fixture Area C').click();
  const assessment = page.locator('section.assessment');
  await expect(assessment.getByRole('status')).toContainText('Unrated: insufficient evidence');
  await page.getByRole('tab', { name: /Housing support/ }).click();
  await expect(assessment.getByRole('status')).toContainText('Unrated: insufficient evidence');
  await expect(assessment).not.toContainText('Exploratory score');

  await areaButton(page, 'Fixture Area A').click();
  await assessment.getByRole('button', { name: /View housing evidence/ }).click();
  const broken = page.locator('[data-evidence-id="fixture-a-res-5"]');
  await broken.scrollIntoViewIfNeeded();
  await expect(broken.getByRole('note')).toContainText('Image could not be loaded');
  await expect(broken).toContainText('No construction or reconstruction visible');
});

test('keyboard users can switch modes, pick an area and open evidence', async ({ page }) => {
  await page.getByRole('tab', { name: /Support businesses/ }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: /Housing support/ })).toBeFocused();
  await expect(page.getByRole('tab', { name: /Housing support/ })).toHaveAttribute('aria-selected', 'true');

  const areaD = areaButton(page, 'Fixture Area D');
  await areaD.focus();
  await page.keyboard.press('Enter');
  await expect(areaD).toHaveAttribute('aria-pressed', 'true');

  const evidenceButton = page.getByRole('button', { name: /View housing evidence/ });
  await evidenceButton.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog', { name: 'Housing evidence' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(evidenceButton).toBeFocused();
});

test('layout has no horizontal overflow', async ({ page }) => {
  for (const mode of [/Support businesses/, /Housing support/]) {
    await page.getByRole('tab', { name: mode }).click();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  }
});

test('missing real bundle shows an error that points to the labeled fixture', async ({ page }) => {
  await page.route('**/data/demo.json', (route) => route.fulfill({ status: 404, body: 'Not found' }));
  await page.goto('./');
  await expect(page.getByRole('alert')).toContainText('data/demo.json returned HTTP 404');
  await expect(page.getByRole('link', { name: /labeled demo fixture/ })).toHaveAttribute('href', '?data=fixture');
});

test('real pipeline: business actions, missing ratings, Census evidence and housing resources', async ({ page }) => {
  await page.goto('?data=demo');
  await page.getByRole('navigation').getByRole('button', { name: /Tract 06037601001/ }).click();
  const assessment = page.locator('section.assessment');
  await expect(assessment).toContainText('Unrated: insufficient evidence');
  const business = page.getByRole('listitem', { name: "Dulan's Soul Food Kitchen" });
  await expect(business.getByRole('link', { name: /Visit website/ })).toHaveAttribute('href', 'https://www.dulans-sfk.com/');
  await assessment.getByRole('button', { name: /View commercial evidence/ }).click();
  const drawer = page.getByRole('dialog', { name: 'Commercial evidence' });
  await expect(drawer).toContainText('U.S. Census Bureau');
  await drawer.getByRole('button', { name: 'Close' }).click();
  await page.getByRole('tab', { name: /Housing support/ }).click();
  await expect(page.getByRole('heading', { name: 'Housing area vulnerability' })).toBeVisible();
  await expect(page.getByRole('link', { name: /Housing Protection/ })).toBeVisible();
});
