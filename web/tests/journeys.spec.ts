import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function selectArea(page: Page, label: string): Promise<void> {
  await page.getByRole('button', { name: 'Browse all places' }).click();
  await page.getByRole('navigation', { name: 'Places and areas' }).getByRole('button', { name: new RegExp(label) }).click();
}
const evidenceTab = (page: Page) => page.getByRole('tab', { name: 'Evidence', exact: true });
const supportTab = (page: Page) => page.getByRole('tab', { name: 'Local support', exact: true });

test('real business search → facts → evidence → housing resources', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('searchbox').fill('Dulan');
  await page.getByRole('navigation').getByRole('button', { name: /Dulan.*Manchester/ }).click();
  const panel = page.getByRole('region', { name: 'Location details' });
  await expect(panel.getByRole('heading', { name: "Dulan's Soul Food Kitchen" })).toBeVisible();
  await expect(panel.getByText('58.7%')).toBeVisible();
  await expect(panel.getByRole('link', { name: 'Visit website', exact: true })).toHaveAttribute('href', 'https://www.dulans-sfk.com/');
  await evidenceTab(page).click();
  await page.getByRole('button', { name: /View commercial evidence/ }).click();
  const drawer = page.getByRole('dialog', { name: 'Commercial evidence' });
  await expect(drawer).toContainText('U.S. Census Bureau');
  await page.keyboard.press('Escape');
  await expect(drawer).toBeHidden();
  await page.getByRole('tab', { name: 'Housing support' }).click();
  await supportTab(page).click();
  await expect(panel.getByRole('link', { name: /Housing Protection/ })).toBeVisible();
  await page.getByRole('button', { name: 'Close location details' }).click();
  await expect(panel).toBeHidden();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
});

test('live city map renders buildings and markers; view controls and marker selection work', async ({ page }) => {
  await page.goto('/');
  const flat = page.getByRole('button', { name: '2D view', exact: true });
  await expect(flat).toBeEnabled({ timeout: 45000 });
  await expect(page.locator('.maplibregl-canvas')).toBeVisible();
  await expect(page.locator('.city-marker')).toHaveCount(5);
  // Real map pixels are inspected alongside these live, unmocked interactions.
  const marker = page.getByRole('button', { name: 'Explore Hilltop Coffee + Kitchen', exact: true });
  await marker.click();
  await expect(page.getByRole('region', { name: 'Location details' }).getByRole('heading', { name: 'Hilltop Coffee + Kitchen' })).toBeVisible();
  await flat.click();
  await expect(page.getByRole('button', { name: '3D view', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '3D view', exact: true }).click();
  await expect(page.getByRole('button', { name: '2D view', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Reset map to Inglewood' }).click();
  await page.screenshot({ path: test.info().outputPath('city-selected.png') });
});

test('map failure leaves search and source-backed information usable', async ({ page }) => {
  await page.route('https://tiles.openfreemap.org/**', route => route.abort());
  await page.goto('/');
  await expect(page.getByText('City map unavailable')).toBeVisible({ timeout: 25000 });
  await page.getByRole('searchbox').fill('Dulan');
  await page.getByRole('navigation').getByRole('button', { name: /Dulan.*Manchester/ }).click();
  await expect(page.getByText('58.7%')).toBeVisible();
});

test('fixture scores, missing inputs, comparison and evidence survive the new navigation', async ({ page }) => {
  await page.goto('?data=fixture');
  await expect(page.getByRole('note').first()).toContainText('Synthetic demo');
  await selectArea(page, 'Fixture Area A');
  await evidenceTab(page).click();
  await expect(page.locator('section.assessment')).toContainText('Exploratory score 68.4 out of 100');
  await page.getByRole('tab', { name: 'Housing support' }).click();
  await supportTab(page).click();
  await page.getByLabel(/Compare Fixture Area A with/).selectOption('fixture-d');
  await expect(page.getByRole('table', { name: /Housing factors for/ })).toContainText('Lower · 18.6/100');
  await evidenceTab(page).click();
  await page.getByRole('button', { name: /View housing evidence/ }).click();
  const drawer = page.getByRole('dialog', { name: 'Housing evidence' });
  await expect(drawer.getByText('Residential frontage').first()).toBeVisible();
  const broken = drawer.locator('[data-evidence-id="fixture-a-res-5"]');
  await broken.scrollIntoViewIfNeeded();
  await expect(broken.getByRole('note')).toContainText('Image could not be loaded');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: /View housing evidence/ })).toBeFocused();
  await selectArea(page, 'Fixture Area C');
  await evidenceTab(page).click();
  await expect(page.locator('section.assessment')).toContainText('Combined assessment pending');
  await expect(page.locator('section.assessment')).not.toContainText('Exploratory score');
});

test('historical story preserves real photographs, attribution and limitations', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /Street stories/ }).click();
  const dialog = page.getByRole('dialog', { name: 'Historical street stories' });
  await expect(dialog.getByRole('heading', { name: 'One commercial street, two dates' })).toBeVisible();
  await expect(dialog.getByText('May 20, 2019')).toBeVisible();
  await expect(dialog.getByText('January 9, 2020')).toBeVisible();
  for (const image of await dialog.getByRole('img').all()) {
    await image.scrollIntoViewIfNeeded();
    await expect.poll(() => image.evaluate(el => (el as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  }
  await expect(dialog.getByRole('link', { name: 'Earlier Mapillary source' })).toHaveAttribute('href', 'https://www.mapillary.com/app/?pKey=3672049312922199');
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(page.getByRole('button', { name: /Street stories/ })).toBeFocused();
});

test('historical model remains separately labeled and its score remains inspectable', async ({ page }) => {
  await page.goto('?data=clip');
  await expect(page.getByRole('note').first()).toContainText('Historical multimodal prototype');
  await selectArea(page, '6014.01');
  await evidenceTab(page).click();
  await expect(page.locator('section.assessment')).toContainText('CLIP contributes 1.23');
  await page.getByRole('button', { name: /View commercial evidence/ }).click();
  await expect(page.getByRole('dialog', { name: 'Commercial evidence' }).getByRole('img')).toHaveCount(2);
});

test('keyboard navigation, empty search and data errors are accessible', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('tab', { name: 'Support businesses' }).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', { name: 'Housing support' })).toBeFocused();
  await page.getByRole('searchbox').fill('no-such-location');
  await expect(page.getByText(/No matching places/)).toBeVisible();
  await page.route('**/data/demo.json', route => route.fulfill({ status: 404, body: 'Not found' }));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('data/demo.json returned HTTP 404');
});

test('short landscape screens keep location details scrollable', async ({ page }) => {
  await page.setViewportSize({ width: 667, height: 375 });
  await page.goto('/');
  await page.getByRole('searchbox').fill('Hilltop');
  await page.getByRole('navigation').getByRole('button', { name: /Hilltop Coffee/ }).click();
  const content = page.locator('.location-content');
  expect(await content.evaluate(el => el.clientHeight)).toBeGreaterThan(100);
  await expect(page.getByRole('link', { name: 'Visit website', exact: true })).toBeVisible();
  await evidenceTab(page).click();
  await page.getByRole('button', { name: /View commercial evidence/ }).click();
  await expect(page.getByRole('dialog', { name: 'Commercial evidence' })).toBeVisible();
});

test('all five business overviews load their own sourced photo', async ({ page }) => {
  await page.goto('/');
  for (const name of ["Dulan's Soul Food Kitchen", 'Hilltop Coffee + Kitchen', 'The Serving Spoon', 'Sweet Red Peach', 'The Toast & Jam']) {
    await page.getByRole('searchbox').fill(name);
    await page.getByRole('navigation').getByRole('button', { name: new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) }).click();
    const panel = page.getByRole('region', { name: 'Location details' });
    await expect(panel.getByRole('heading', { name, exact: true })).toBeVisible();
    const photo = panel.locator('.business-photo img');
    await expect(photo).toBeVisible();
    await expect.poll(() => photo.evaluate(el => (el as HTMLImageElement).naturalWidth), { timeout: 15000 }).toBeGreaterThan(0);
    await expect(panel.getByRole('link', { name: 'Photo source' })).toHaveAttribute('href', /^https:\/\//);
  }
  expect(await page.locator('.location-panel-header h2').evaluate(el => getComputedStyle(el).fontFamily)).not.toMatch(/Georgia|Times/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(0);
  await page.screenshot({ path: test.info().outputPath('business-photo.png') });
});

test('failed business photo keeps details usable and another business can still load', async ({ page }) => {
  await page.route('**/Dulans-Manch-Dining-1920w.jpg', route => route.abort());
  await page.goto('/');
  await page.getByRole('searchbox').fill('Dulan');
  await page.getByRole('navigation').getByRole('button', { name: /Dulan.*Manchester/ }).click();
  await expect(page.getByText(/^Photo unavailable/)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Visit website', exact: true })).toBeVisible();
  await page.getByRole('searchbox').fill('Hilltop');
  await page.getByRole('navigation').getByRole('button', { name: /Hilltop Coffee/ }).click();
  await expect.poll(() => page.locator('.business-photo img').evaluate(el => (el as HTMLImageElement).naturalWidth), { timeout: 15000 }).toBeGreaterThan(0);
  await expect(page.getByText(/^Photo unavailable/)).toHaveCount(0);
});

test('visible dataset switch leads to historical examples and dated neighborhood context', async ({ page }) => {
  await page.goto('/');
  const views = page.getByRole('navigation', { name: 'Explore views' });
  await expect(views.getByRole('link', { name: 'Explore today' })).toHaveAttribute('aria-current', 'page');
  await page.getByRole('searchbox').fill('Dulan');
  await page.getByRole('navigation', { name: 'Places and areas' }).getByRole('button', { name: /Dulan.*Manchester/i }).click();
  await expect(page.getByText(/Today’s pressure score: \d+\.\d \/ 100/)).toBeVisible();
  await expect(page.getByText(/Rough score from Census data only/)).toBeVisible();
  await expect(page.getByRole('region', { name: 'Five-year outlook' })).toContainText('Will rents outpace incomes?');
  const summary = page.getByRole('region', { name: 'Neighborhood indicators' });
  await expect(summary).toContainText('these indicators do not affect the score');
  await expect(summary).toContainText('2025 roll');
  await summary.getByRole('button', { name: 'View indicator sources' }).click();
  await expect(page.getByRole('dialog', { name: 'Commercial evidence' })).toContainText('Assessor roll');
  await page.keyboard.press('Escape');
  await views.getByRole('link', { name: 'Historical analysis' }).click();
  await expect(page).toHaveURL(/data=clip/);
  await expect(views.getByRole('link', { name: 'Historical analysis' })).toHaveAttribute('aria-current', 'page');
  await page.getByRole('button', { name: /Housing example/ }).click();
  await expect(page.getByRole('tab', { name: 'Housing support' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByText(/Today’s pressure score: 38.6/)).toBeVisible();
  await expect(page.getByRole('region', { name: 'Five-year outlook' })).toContainText('What happened');
  await expect(summary).toContainText('2020 roll');
  await expect(summary).not.toContainText('2025');
  await expect(summary).not.toContainText('ZIP');
  await page.getByText('Opening Inglewood…', { exact: true }).waitFor({ state: 'hidden', timeout: 25000 });
  await summary.scrollIntoViewIfNeeded();
  await page.screenshot({ animations: 'disabled', path: `../.Codex/plans/historical-overview-${test.info().project.name}.png` });
  await page.getByRole('button', { name: 'Close location details' }).click();
  const toolsBox = await page.getByRole('region', { name: 'Find a place' }).boundingBox();
  const introBox = await page.locator('.city-intro').boundingBox();
  expect(introBox!.y).toBeGreaterThan(toolsBox!.y + toolsBox!.height);
  await page.screenshot({ animations: 'disabled', path: `../.Codex/plans/historical-home-${test.info().project.name}.png` });
  await page.getByRole('button', { name: /Commercial example/ }).click();
  await expect(page.getByText(/Today’s pressure score: 16.1/)).toBeVisible();
  await views.getByRole('link', { name: 'Explore today' }).click();
  await expect(page).toHaveURL(/data=demo/);
  await expect(page.getByRole('button', { name: /Housing example/ })).toHaveCount(0);
  await page.getByText('Opening Inglewood…', { exact: true }).waitFor({ state: 'hidden', timeout: 25000 });
  await page.screenshot({ animations: 'disabled', path: `../.Codex/plans/explore-home-${test.info().project.name}.png` });
});

test('area explanation connects dated changes to local business and housing actions', async ({ page }) => {
  await page.goto('/');
  await selectArea(page, '6010.01');
  const story = page.getByRole('region', { name: 'What changed here' });
  await expect(story).toContainText('rose from');
  await expect(story).toContainText('2016–2020');
  await expect(story).toContainText('2021–2025');
  await expect(story).toContainText('not proof of displacement');
  await story.getByRole('button', { name: 'Check the evidence' }).click();
  await expect(page.getByRole('dialog', { name: 'Commercial evidence' })).toContainText('Assessor roll');
  await page.keyboard.press('Escape');
  await page.getByRole('tab', { name: 'Housing support' }).click();
  const actions = page.getByRole('region', { name: 'What you can do' });
  await expect(actions.getByRole('link', { name: /Housing Protection/ })).toHaveAttribute('href', /^https:\/\//);
  await expect(actions).toContainText('Serves: City of Inglewood');
  await actions.getByRole('button', { name: 'View resources and compare areas' }).click();
  await expect(page.getByRole('combobox')).toBeVisible();
  await page.getByRole('tab', { name: 'Overview', exact: true }).click();
  await story.scrollIntoViewIfNeeded();
  await page.getByText('Opening Inglewood…', { exact: true }).waitFor({ state: 'hidden', timeout: 25000 });
  await page.screenshot({ animations: 'disabled', path: `../.Codex/plans/area-story-${test.info().project.name}.png` });
  await actions.scrollIntoViewIfNeeded();
  await page.screenshot({ animations: 'disabled', path: `../.Codex/plans/area-actions-${test.info().project.name}.png` });
  await page.getByRole('tab', { name: 'Support businesses' }).click();
  await actions.getByRole('button', { name: /Dulan.*Manchester/ }).click();
  await expect(actions.getByRole('link', { name: 'Visit website', exact: true })).toHaveAttribute('href', 'https://www.dulans-sfk.com/');
  await expect(actions.getByRole('link', { name: 'Directions', exact: true })).toHaveAttribute('href', 'https://www.google.com/maps/dir/?api=1&destination=202+E+Manchester+Blvd%2C+Inglewood%2C+CA+90301');
  await page.getByRole('navigation', { name: 'Explore views' }).getByRole('link', { name: 'Historical analysis' }).click();
  await page.getByRole('button', { name: /Housing example/ }).click();
  await expect(story).toContainText('aren’t two comparable periods');
  await expect(actions).toContainText('This view describes the past');
  await actions.getByRole('link', { name: 'Explore today' }).click();
  await expect(page).toHaveURL(/data=demo/);
});
