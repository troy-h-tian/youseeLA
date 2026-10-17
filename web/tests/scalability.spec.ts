import { execSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import { validateBundle } from '../src/data/load';
import type { Bundle } from '../src/data/types';
import { syntheticBundle } from './support/synthetic';

/**
 * Browser responsiveness for Task 8. Runs against the production preview
 * (see playwright.config.ts). Benchmark bundles are injected by intercepting
 * the app's normal data request, so no benchmark route ships in the app.
 *
 * Optional environment:
 *   YOUSEELA_BENCHMARK_DIR   directory of Person A's generated bundles named
 *                            bundle-100.json / bundle-1000.json (used instead
 *                            of the TypeScript generator when present)
 *   YOUSEELA_UI_BENCH_OUTPUT results path (default ../artifacts/ui-scalability.json)
 */

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, '..');
const REPETITIONS = 3;
const SIZES = [100, 1000];
const OUTPUT = process.env.YOUSEELA_UI_BENCH_OUTPUT ?? path.resolve(webRoot, '../artifacts/ui-scalability.json');
const BENCH_IMAGE_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="180"><rect width="320" height="180" fill="#ccc"/></svg>';

interface Dataset {
  name: string;
  source: string;
  json: string;
  bundle: Bundle;
}

function datasets(): Dataset[] {
  const out: Dataset[] = [];
  const demo = path.join(webRoot, 'public/data/demo.json');
  const pilotPath = existsSync(demo) ? demo : path.join(webRoot, 'public/data/fixture.json');
  const pilotJson = readFileSync(pilotPath, 'utf8');
  const pilot = JSON.parse(pilotJson) as Bundle;
  out.push({
    name: pilot.data_kind === 'real' ? 'pilot (real)' : 'pilot (acceptance fixture — real bundle not yet exported)',
    source: path.relative(webRoot, pilotPath),
    json: pilotJson,
    bundle: pilot,
  });
  const dir = process.env.YOUSEELA_BENCHMARK_DIR;
  for (const size of SIZES) {
    const external = dir ? path.join(dir, `bundle-${size}.json`) : null;
    if (external && existsSync(external)) {
      const json = readFileSync(external, 'utf8');
      out.push({ name: `synthetic-${size}`, source: external, json, bundle: JSON.parse(json) as Bundle });
    } else {
      const bundle = syntheticBundle(size);
      out.push({ name: `synthetic-${size}`, source: 'tests/support/synthetic.ts (seed 20261017)', json: JSON.stringify(bundle), bundle });
    }
  }
  return out;
}

async function timeMeasure(page: Page, name: string, action: () => Promise<void>): Promise<number> {
  await page.evaluate((n) => performance.clearMeasures(n), name);
  await action();
  await page.waitForFunction((n) => performance.getEntriesByName(n, 'measure').length > 0, name);
  return page.evaluate((n) => performance.getEntriesByName(n, 'measure').at(-1)!.duration, name);
}

const summarize = (values: number[]) => {
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
  return { median_ms: +median.toFixed(1), max_ms: +Math.max(...values).toFixed(1), runs_ms: values.map((v) => +v.toFixed(1)) };
};

function assetBytes(): Record<string, number> {
  const assets = path.join(webRoot, 'dist/assets');
  if (!existsSync(assets)) return {};
  return Object.fromEntries(readdirSync(assets).map((f) => [f, statSync(path.join(assets, f)).size]));
}

test('UI responsiveness on pilot and synthetic bundles', async ({ browser, browserName }) => {
  const results = [];
  for (const dataset of datasets()) {
    expect(validateBundle(dataset.bundle), `${dataset.name} must be a valid bundle`).toEqual([]);
    const runs = { initial_render: [] as number[], mode_switch: [] as number[], area_select: [] as number[] };

    for (let rep = 0; rep < REPETITIONS; rep += 1) {
      const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
      const page = await context.newPage();
      await page.route('**/data/demo.json', (route) =>
        route.fulfill({ status: 200, contentType: 'application/json', body: dataset.json }),
      );
      await page.route('**/bench-images/**', (route) =>
        route.fulfill({ status: 200, contentType: 'image/svg+xml', body: BENCH_IMAGE_SVG }),
      );

      await page.goto('./');
      await page.waitForFunction(() => performance.getEntriesByName('youseela:initial-render', 'measure').length > 0);
      runs.initial_render.push(
        await page.evaluate(() => performance.getEntriesByName('youseela:initial-render', 'measure')[0]!.duration),
      );

      runs.mode_switch.push(
        await timeMeasure(page, 'youseela:mode-switch', () => page.getByRole('tab', { name: /Housing support/ }).click()),
      );
      await expect(page.getByRole('tab', { name: 'Housing support' })).toHaveAttribute('aria-selected', 'true');
      await page.getByRole('button', { name: 'Browse all places' }).click();

      // Select the last listed area so the content genuinely changes.
      const target = page.getByRole('navigation').getByRole('button').last();
      const label = (await target.locator('strong').textContent())!;
      runs.area_select.push(await timeMeasure(page, 'youseela:area-select', () => target.click()));
      await expect(page.locator('.location-panel-header h2')).toContainText(label);

      await context.close();
    }

    results.push({
      dataset: dataset.name,
      source: dataset.source,
      data_kind: dataset.bundle.data_kind,
      counts: {
        areas: dataset.bundle.areas.length,
        businesses: dataset.bundle.businesses.length,
        evidence: dataset.bundle.evidence.length,
        image_references: dataset.bundle.evidence.filter((e) => e.image_url).length,
      },
      bundle_bytes: Buffer.byteLength(dataset.json),
      initial_render: summarize(runs.initial_render),
      mode_switch: summarize(runs.mode_switch),
      area_select: summarize(runs.area_select),
    });
  }

  let commit = 'unknown';
  try {
    commit = execSync('git rev-parse --short HEAD', { cwd: webRoot }).toString().trim();
  } catch {
    /* not a git checkout */
  }
  const report = {
    label: 'UI performance measurements on labeled fixtures; not evidence of model validity.',
    measured_at: new Date().toISOString(),
    commit,
    command: 'npm --prefix web run test:scalability',
    repetitions: REPETITIONS,
    definitions: {
      initial_render: 'Navigation start until the first paint after the loaded bundle is committed (includes fetch, JSON parse, validation and render).',
      mode_switch: 'Business → Housing tab click handler until the first macrotask after the next animation frame following the React commit.',
      area_select: 'Area list click handler until the first macrotask after the next animation frame following the React commit.',
      exclusions: 'UI shell and data interactions only; map tile loading, WebGL readiness, camera animation and external imagery delivery are not measured.',
    },
    environment: {
      browser: `${browserName} ${browser.version()}`,
      viewport: '1280x800',
      build: 'vite production build served by vite preview',
      os: `${os.platform()} ${os.release()} ${os.arch()}`,
      cpu: os.cpus()[0]?.model ?? 'unknown',
      cpu_count: os.cpus().length,
      memory_gb: +(os.totalmem() / 1024 ** 3).toFixed(1),
      node: process.version,
    },
    app_asset_bytes: assetBytes(),
    results,
  };
  mkdirSync(path.dirname(OUTPUT), { recursive: true });
  writeFileSync(OUTPUT, JSON.stringify(report, null, 2) + '\n');
  console.table(
    results.map((r) => ({
      dataset: r.dataset,
      areas: r.counts.areas,
      kb: Math.round(r.bundle_bytes / 1024),
      'initial ms (med/max)': `${r.initial_render.median_ms}/${r.initial_render.max_ms}`,
      'mode ms (med/max)': `${r.mode_switch.median_ms}/${r.mode_switch.max_ms}`,
      'select ms (med/max)': `${r.area_select.median_ms}/${r.area_select.max_ms}`,
    })),
  );
});
