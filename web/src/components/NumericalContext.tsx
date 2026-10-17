import type { Area } from '../data/types';
import { contextIndicator } from '../lib/context';
import { formatIndicator, formatMoe } from '../lib/format';

export function NumericalContext({ area }: { area: Area }) {
  const burden = contextIndicator(area, 'rent_burden_share');
  const renters = contextIndicator(area, 'renter_share');
  const available = [burden, renters].filter((item) => item !== undefined);
  if (!available.length) return null;
  const periods = [...new Set(available.map((item) => item.source_period))].join(', ');
  return (
    <section className="numerical-context" aria-label="Census housing context">
      <h3>What the Census data shows</h3>
      <p className="muted">ACS five-year estimates · <span>{periods}</span> · full Census tract</p>
      <div className="context-metrics">
        {burden && <div><span>Rent burden</span><strong>{formatIndicator(burden)}</strong>
          <p>Of renter households with a computable rent-to-income ratio, spending at least 30% of income on rent.</p>
          {formatMoe(burden) && <small>{formatMoe(burden)}</small>}</div>}
        {renters && <div><span>Renter share</span><strong>{formatIndicator(renters)}</strong>
          <p>Of occupied households that rent their home.</p>
          {formatMoe(renters) && <small>{formatMoe(renters)}</small>}</div>}
      </div>
      <p className="context-note">These describe housing conditions during the stated period, not changes over time or an individual business’s finances.
        {available.some((item) => item.margin_of_error === null) && ' Derived-share margins of error are not available in this export.'}</p>
    </section>
  );
}
