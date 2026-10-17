/**
 * Public bundle contract, schema version 1.
 *
 * Mirrors the "Data contract before parallel work" section of
 * Implementation-Plan.txt. Person A's Pydantic models in
 * src/youseela/contracts.py must serialize to exactly these field names;
 * neither side renames fields without agreeing first.
 *
 * Conventions:
 * - Missing values are `null`, never 0. The UI never fills a gap with zero.
 * - Dates are ISO 8601 strings (YYYY-MM-DD, or full timestamps for generated_at).
 * - Scores are 0–100 points on an exploratory rubric, not probabilities.
 */

export const SCHEMA_VERSION = 1;

export type DataKind = 'real' | 'fixture';

/** The two assessment configurations exported for every area. */
export type AssessmentKind = 'housing' | 'commercial';

/** UI modes. Business mode shows the commercial assessment. */
export type Mode = 'business' | 'housing';

export const ASSESSMENT_FOR_MODE: Record<Mode, AssessmentKind> = {
  business: 'commercial',
  housing: 'housing',
};

export interface Bundle {
  schema_version: number;
  generated_at: string;
  data_kind: DataKind;
  methodology: Methodology;
  areas: Area[];
  businesses: Business[];
  resources: Resource[];
  evidence: Evidence[];
}

export interface Methodology {
  config_version: string;
  /** Plain-language description of what the scores mean and do not mean. */
  summary: string;
  limitations: string[];
  /** Upper bounds (exclusive) for the lower and moderate tiers, e.g. 33 and 67. */
  tier_bands: { lower_below: number; moderate_below: number };
  /** Rubric formula per assessment, for display only. */
  formulas: Record<AssessmentKind, string>;
}

export type Geometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] };

export interface Area {
  /** Stable Census tract GEOID (11 digits) for real data. */
  id: string;
  label: string;
  /** Boundary in WGS84 longitude/latitude, matching the ACS vintage. */
  boundary: Geometry;
  /** Note about the boundary, e.g. that the tract extends beyond city limits. */
  boundary_note: string | null;
  indicators: Indicator[];
  /** External benchmark classification (Urban Displacement Project); never a score input. */
  reference_typology?: ReferenceTypology | null;
  housing: Assessment;
  commercial: Assessment;
}

export interface ReferenceTypology {
  code: string;
  label: string;
  source_period: string;
  evidence_ids: string[];
}

export interface Indicator {
  key: string;
  label: string;
  value: number | null;
  /** 'share' values are 0–1 fractions; others are displayed with the unit text. */
  unit: 'share' | 'usd' | 'count' | 'ratio';
  source_period: string;
  margin_of_error: number | null;
  numerator: number | null;
  denominator: number | null;
  evidence_ids: string[];
  /** Why the value is null, when it is. */
  unavailable_reason: string | null;
}

export type AssessmentStatus = 'rated' | 'insufficient_evidence';
export type Tier = 'lower' | 'moderate' | 'higher';

export interface Assessment {
  status: AssessmentStatus;
  /** 0–100 when rated; null when insufficient_evidence. */
  score: number | null;
  score_range?: { lower: number; upper: number; explanation: string } | null;
  /** Null when insufficient_evidence. */
  tier: Tier | null;
  /** Specific reason the area is unrated; null when rated. */
  unrated_reason: string | null;
  contributions: Contribution[];
  warnings: string[];
  evidence_ids: string[];
  config_version: string;
  coverage: Coverage;
}

export interface Contribution {
  /** Rubric term id, e.g. 'B', 'P', 'Vh*P'. */
  feature: string;
  label: string;
  /** Rubric weight, e.g. 0.6. */
  weight: number;
  /** Term value in [0, 1] before weighting; null when unavailable. */
  value: number | null;
  /** Points added to the 0–100 score: 100 × weight × value. */
  points: number | null;
  /** Human-readable formula for this term, e.g. "100 × 0.15 × Vh × P". */
  formula: string;
  numerator: number | null;
  denominator: number | null;
  evidence_ids: string[];
  /** Explanation when value is null or the term is gated. */
  note: string | null;
}

export interface Coverage {
  /** Distinct reviewed locations for the mode's frontage class. */
  distinct_locations: number;
  /** Assessable unique relevant frontages. */
  assessable_frontages: number;
  required_locations: number;
  required_frontages: number;
  /** Earliest and latest image capture dates used, if any. */
  capture_date_range: [string, string] | null;
}

export interface Location {
  lat: number;
  lon: number;
}

export interface Business {
  id: string;
  name: string;
  address: string;
  location: Location;
  area_id: string;
  category: string;
  /** Short local description supported by the source. */
  description: string;
  /** Why this business is shown, phrased as area context. */
  rationale: string;
  source_url: string;
  verified_at: string;
  website_url: string | null;
  /** Optional override; otherwise directions are derived from location. */
  directions_url: string | null;
}

export type ResourceKind = 'housing' | 'business';

export interface Resource {
  id: string;
  name: string;
  kind: ResourceKind;
  description: string;
  url: string;
  /** Who the resource serves, e.g. "City of Inglewood residents". */
  service_area: string;
  /** Area ids the resource applies to; null means every pilot area. */
  area_ids: string[] | null;
  source_url: string;
  verified_at: string;
}

export type EvidenceType =
  | 'image'
  | 'census'
  | 'project_record'
  | 'business_listing'
  | 'assessor_roll'
  | 'business_patterns'
  | 'reference_typology';
export type FrontageClass = 'residential' | 'commercial';
export type ObservationStatus = 'present' | 'absent' | 'unclear';

export interface Evidence {
  id: string;
  evidence_type: EvidenceType;
  area_id: string | null;
  title: string;
  source_url: string;
  attribution: string;
  license: string;
  /** Image capture date, or source publication date for non-image evidence. */
  captured_at: string;
  location: Location | null;
  frontage_class: FrontageClass | null;
  /** Public image URL with confirmed distribution rights, if any. */
  image_url: string | null;
  reviewed: boolean;
  observations: ImageObservation[];
  /** Human-review corrections applied to the model output. */
  corrections: string[];
}

export interface ImageObservation {
  feature: string;
  label: string;
  status: ObservationStatus;
  /** Null when the source records status but no measured object count. */
  visible_count: number | null;
  description: string;
}
