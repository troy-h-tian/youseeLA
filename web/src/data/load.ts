import { SCHEMA_VERSION } from './types';
import type { Assessment, Bundle } from './types';

export type DataSource = 'demo' | 'fixture';

export const DATA_PATHS: Record<DataSource, string> = {
  demo: 'data/demo.json',
  fixture: 'data/fixture.json',
};

export class BundleError extends Error {
  readonly problems: string[];

  constructor(message: string, problems: string[] = []) {
    super(message);
    this.name = 'BundleError';
    this.problems = problems;
  }
}

/**
 * Picks the bundle to load. `?data=fixture` selects the labeled development
 * fixture; the real pipeline output (demo.json) is the default unless the
 * build sets VITE_DATA_SOURCE=fixture.
 */
export function resolveDataSource(search: string, envDefault?: string): DataSource {
  const requested = new URLSearchParams(search).get('data');
  if (requested === 'fixture' || requested === 'demo') return requested;
  return envDefault === 'fixture' ? 'fixture' : 'demo';
}

export async function loadBundle(
  source: DataSource,
  fetchImpl: typeof fetch = fetch,
): Promise<Bundle> {
  let response: Response;
  try {
    response = await fetchImpl(DATA_PATHS[source], { cache: 'no-cache' });
  } catch (error) {
    throw new BundleError(`Could not reach ${DATA_PATHS[source]}: ${String(error)}`);
  }
  if (!response.ok) {
    throw new BundleError(`${DATA_PATHS[source]} returned HTTP ${response.status}.`);
  }
  let raw: unknown;
  try {
    raw = await response.json();
  } catch {
    throw new BundleError(`${DATA_PATHS[source]} is not valid JSON.`);
  }
  const problems = validateBundle(raw);
  if (problems.length > 0) {
    throw new BundleError(`${DATA_PATHS[source]} does not match the data contract.`, problems);
  }
  return raw as Bundle;
}

const isObject = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/**
 * Checks the invariants the UI relies on. Returns human-readable problems;
 * an empty list means the bundle is usable. This is a guard against
 * integration drift, not a replacement for the pipeline's export validation.
 */
export function validateBundle(raw: unknown): string[] {
  const problems: string[] = [];
  if (!isObject(raw)) return ['Bundle is not a JSON object.'];

  if (raw.schema_version !== SCHEMA_VERSION) {
    problems.push(`schema_version must be ${SCHEMA_VERSION}, got ${JSON.stringify(raw.schema_version)}.`);
  }
  if (raw.data_kind !== 'real' && raw.data_kind !== 'fixture') {
    problems.push(`data_kind must be "real" or "fixture", got ${JSON.stringify(raw.data_kind)}.`);
  }
  if (typeof raw.generated_at !== 'string') problems.push('generated_at is missing.');
  if (!isObject(raw.methodology)) problems.push('methodology is missing.');
  for (const key of ['areas', 'businesses', 'resources', 'evidence'] as const) {
    if (!Array.isArray(raw[key])) problems.push(`${key} must be an array.`);
  }
  if (problems.length > 0) return problems;

  const bundle = raw as unknown as Bundle;
  const evidenceIds = new Set<string>();
  for (const item of bundle.evidence) {
    if (evidenceIds.has(item.id)) problems.push(`Duplicate evidence id ${item.id}.`);
    evidenceIds.add(item.id);
  }
  const checkRefs = (ids: unknown, where: string) => {
    if (!Array.isArray(ids)) {
      problems.push(`${where}: evidence_ids must be an array.`);
      return;
    }
    for (const id of ids) {
      if (!evidenceIds.has(id as string)) problems.push(`${where} references missing evidence ${String(id)}.`);
    }
  };

  const areaIds = new Set<string>();
  for (const area of bundle.areas) {
    if (typeof area.id !== 'string' || area.id === '') {
      problems.push('An area is missing its id.');
      continue;
    }
    if (areaIds.has(area.id)) problems.push(`Duplicate area id ${area.id}.`);
    areaIds.add(area.id);
    if (!isObject(area.boundary)) problems.push(`Area ${area.id} has no boundary.`);
    for (const kind of ['housing', 'commercial'] as const) {
      problems.push(...validateAssessment(area[kind], `Area ${area.id} ${kind}`));
      if (isObject(area[kind])) {
        checkRefs(area[kind].evidence_ids, `Area ${area.id} ${kind}`);
        for (const c of area[kind].contributions ?? []) {
          checkRefs(c.evidence_ids, `Area ${area.id} ${kind} term ${c.feature}`);
        }
      }
    }
    for (const indicator of area.indicators ?? []) {
      checkRefs(indicator.evidence_ids, `Area ${area.id} indicator ${indicator.key}`);
    }
  }

  for (const business of bundle.businesses) {
    if (!areaIds.has(business.area_id)) {
      problems.push(`Business ${business.id} references unknown area ${business.area_id}.`);
    }
  }
  for (const resource of bundle.resources) {
    for (const id of resource.area_ids ?? []) {
      if (!areaIds.has(id)) problems.push(`Resource ${resource.id} references unknown area ${id}.`);
    }
  }
  for (const item of bundle.evidence) {
    if (item.area_id !== null && !areaIds.has(item.area_id)) {
      problems.push(`Evidence ${item.id} references unknown area ${item.area_id}.`);
    }
  }
  return problems;
}

function validateAssessment(value: unknown, where: string): string[] {
  if (!isObject(value)) return [`${where} assessment is missing.`];
  const a = value as unknown as Assessment;
  const problems: string[] = [];
  if (a.score_range != null) {
    const r = a.score_range;
    if (!isObject(r) || !Number.isFinite(r.lower) || !Number.isFinite(r.upper)
        || r.lower < 0 || r.upper > 100 || r.lower > r.upper
        || a.score === null || a.score < r.lower || a.score > r.upper
        || typeof r.explanation !== 'string') problems.push(`${where} has an invalid sensitivity range.`);
  }
  if (a.status === 'rated') {
    if (typeof a.score !== 'number' || !Number.isFinite(a.score) || a.score < 0 || a.score > 100) {
      problems.push(`${where} is rated but score ${JSON.stringify(a.score)} is not within 0–100.`);
    }
    if (a.tier !== 'lower' && a.tier !== 'moderate' && a.tier !== 'higher') {
      problems.push(`${where} is rated but has no tier.`);
    }
  } else if (a.status === 'insufficient_evidence') {
    if (a.score !== null || a.tier !== null) {
      problems.push(`${where} has insufficient evidence but a non-null score or tier.`);
    }
    if (!a.unrated_reason) problems.push(`${where} is unrated without a reason.`);
  } else {
    problems.push(`${where} has unknown status ${JSON.stringify(a.status)}.`);
  }
  if (!Array.isArray(a.contributions)) problems.push(`${where} contributions must be an array.`);
  if (!isObject(a.coverage)) problems.push(`${where} coverage is missing.`);
  return problems;
}

