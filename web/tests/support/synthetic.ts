import type { Area, Assessment, AssessmentKind, Bundle, Business, Contribution, Evidence } from '../../src/data/types';

/**
 * Deterministic PERFORMANCE FIXTURE generator for UI timings only.
 * Records are invented, labeled as fixtures, and never written into
 * public/data. Person A's Python generator (youseela.benchmark) is the
 * source of record for pipeline timings; this one exists so the browser
 * harness can run without it. Use YOUSEELA_BENCHMARK_DIR to load theirs.
 */

const WEIGHTS: Record<AssessmentKind, { B: number; P: number; V: number }> = {
  housing: { B: 0.6, P: 0.25, V: 0.15 },
  commercial: { B: 0.3, P: 0.5, V: 0.2 },
};
export const IMAGES_PER_AREA = 6;
export const BENCH_IMAGE = 'bench-images/frontage.svg';

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const round = (n: number, d = 4) => Math.round(n * 10 ** d) / 10 ** d;

export function syntheticBundle(size: number, seed = 20261017): Bundle {
  const rand = mulberry32(seed + size);
  const cols = Math.ceil(Math.sqrt(size));
  const cell = 0.004;
  const areas: Area[] = [];
  const evidence: Evidence[] = [];
  const businesses: Business[] = [];

  for (let i = 0; i < size; i += 1) {
    const id = `perf-${String(i + 1).padStart(4, '0')}`;
    const lon = -118.4 + (i % cols) * cell;
    const lat = 34.0 - Math.floor(i / cols) * cell;
    const censusId = `${id}-census`;
    evidence.push(makeEvidence(censusId, id, 'census', null, lat, lon));
    const imageIds: Record<AssessmentKind, string[]> = { housing: [], commercial: [] };
    for (let k = 0; k < IMAGES_PER_AREA; k += 1) {
      const kind: AssessmentKind = k % 2 === 0 ? 'housing' : 'commercial';
      const evId = `${id}-img-${k + 1}`;
      evidence.push(makeEvidence(evId, id, 'image', kind === 'housing' ? 'residential' : 'commercial', lat, lon, rand() < 0.3));
      imageIds[kind].push(evId);
    }

    const B = round(0.2 + rand() * 0.6);
    const historyMissing = rand() < 0.1;
    const P = historyMissing ? null : round(rand() < 0.25 ? 0 : rand());
    const assess = (kind: AssessmentKind): Assessment => {
      const coverageOk = rand() > 0.15;
      const V = coverageOk ? round(Math.floor(rand() * 4) / 3) : null;
      const rated = P !== null && V !== null;
      const w = WEIGHTS[kind];
      const term = (feature: string, label: string, weight: number, value: number | null, ids: string[]): Contribution => ({
        feature,
        label,
        weight,
        value,
        points: rated && value !== null ? round(100 * weight * value, 1) : null,
        formula: `100 × ${weight.toFixed(2)} × ${feature}`,
        numerator: null,
        denominator: null,
        evidence_ids: ids,
        note: value === null ? 'Unavailable in performance fixture.' : null,
      });
      const contributions = [
        term('B', 'Rent-burden share', w.B, B, [censusId]),
        term('P', 'Affordability-change gap', w.P, P, [censusId]),
        term('V*P', 'Corroborated redevelopment × P', w.V, V === null || P === null ? null : round(V * P), imageIds[kind]),
      ];
      const score = rated ? round(contributions.reduce((s, c) => s + (c.points ?? 0), 0), 1) : null;
      return {
        status: rated ? 'rated' : 'insufficient_evidence',
        score,
        tier: score === null ? null : score < 33 ? 'lower' : score < 67 ? 'moderate' : 'higher',
        unrated_reason: rated ? null : historyMissing ? 'Performance fixture: P unavailable.' : 'Performance fixture: coverage below minimum.',
        contributions,
        warnings: ['Performance fixture — not a real assessment.'],
        evidence_ids: [censusId, ...imageIds[kind]],
        config_version: 'perf-fixture',
        coverage: {
          distinct_locations: coverageOk ? 3 : 1,
          assessable_frontages: coverageOk ? 5 : 1,
          required_locations: 3,
          required_frontages: 5,
          capture_date_range: ['2025-03-01', '2025-05-01'],
        },
      };
    };

    areas.push({
      id,
      label: `Performance fixture area ${String(i + 1).padStart(4, '0')}`,
      boundary: {
        type: 'Polygon',
        coordinates: [[[lon, lat], [lon + cell, lat], [lon + cell, lat + cell], [lon, lat + cell], [lon, lat]]],
      },
      boundary_note: 'Performance fixture geometry.',
      indicators: [
        {
          key: 'rent_burden_share',
          label: 'Rent-burden share',
          value: B,
          unit: 'share',
          source_period: 'fixture',
          margin_of_error: null,
          numerator: null,
          denominator: null,
          evidence_ids: [censusId],
          unavailable_reason: null,
        },
      ],
      housing: assess('housing'),
      commercial: assess('commercial'),
    });
    businesses.push({
      id: `${id}-biz`,
      name: `Performance fixture business ${i + 1}`,
      address: 'Fixture address',
      location: { lat: lat + cell / 2, lon: lon + cell / 2 },
      area_id: id,
      category: 'Fixture',
      description: 'Performance fixture business.',
      rationale: 'Performance fixture.',
      source_url: 'https://example.com/perf-fixture',
      verified_at: '2026-10-01',
      website_url: 'https://example.com/perf-fixture',
      directions_url: null,
    });
  }

  return {
    schema_version: 1,
    generated_at: '2026-10-17T00:00:00Z',
    data_kind: 'fixture',
    methodology: {
      config_version: 'perf-fixture',
      summary: `PERFORMANCE FIXTURE with ${size} invented areas (seed ${seed}). Not real places or assessments.`,
      limitations: ['Performance fixture for UI timing only.'],
      tier_bands: { lower_below: 33, moderate_below: 67 },
      formulas: {
        housing: 'Housing = 100 × (0.60·B + 0.25·P + 0.15·Vh·P)',
        commercial: 'Commercial = 100 × (0.30·B + 0.50·P + 0.20·Vc·P)',
      },
    },
    areas,
    businesses,
    resources: [],
    evidence,
  };
}

function makeEvidence(
  id: string,
  areaId: string,
  type: 'census' | 'image',
  frontage: 'residential' | 'commercial' | null,
  lat: number,
  lon: number,
  redevelopment = false,
): Evidence {
  return {
    id,
    evidence_type: type,
    area_id: areaId,
    title: `Performance fixture ${type} ${id}`,
    source_url: 'https://example.org/perf-fixture',
    attribution: 'Performance fixture',
    license: 'Fixture',
    captured_at: '2025-04-01',
    location: { lat, lon },
    frontage_class: frontage,
    image_url: type === 'image' ? BENCH_IMAGE : null,
    reviewed: true,
    observations:
      type === 'image'
        ? [
            {
              feature: 'redevelopment',
              label: 'Corroborated redevelopment work',
              status: redevelopment ? 'present' : 'absent',
              visible_count: redevelopment ? 1 : 0,
              description: 'Performance fixture observation.',
            },
          ]
        : [],
    corrections: [],
  };
}
