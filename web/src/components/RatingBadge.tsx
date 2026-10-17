import type { Assessment } from '../data/types';
import { ratingText } from '../lib/format';

/** Rating chip: tier word plus score, with a pattern class so color is not the only cue. */
export function RatingBadge({ assessment }: { assessment: Assessment }) {
  const tier = assessment.status === 'rated' && !assessment.score_range ? assessment.tier : null;
  return <span className={`rating rating--${tier ?? 'unrated'}`}>{ratingText(assessment)}</span>;
}
