import type { Area, Business, Bundle } from '../../data/types';
import { directionsUrl, formatDate, ratingText } from '../../lib/format';
import { applicableResources, ResourceList } from '../../components/ResourceList';

interface Props {
  bundle: Bundle;
  area: Area;
}

export function BusinessPanel({ bundle, area }: Props) {
  const here = bundle.businesses.filter((b) => b.area_id === area.id);
  const elsewhere = bundle.businesses.filter((b) => b.area_id !== area.id);
  const areas = new Map(bundle.areas.map((a) => [a.id, a] as const));
  const programs = applicableResources(bundle.resources, 'business', area.id);

  return (
    <section className="card" aria-labelledby="businesses-title">
      <h2 id="businesses-title">Local businesses in {area.label}</h2>
      <p className="muted">
        Verified listings. Each card shows the surrounding area&rsquo;s commercial context, which describes the tract —
        not this business&rsquo;s finances, quality or likelihood of closing. No reviews or star ratings are shown.
      </p>
      {here.length === 0 ? (
        <p className="empty">No verified businesses are listed in this area yet.</p>
      ) : (
        <ul className="business-grid">
          {here.map((b) => (
            <BusinessCard key={b.id} business={b} area={area} />
          ))}
        </ul>
      )}

      {elsewhere.length > 0 && (
        <details className="more">
          <summary>Businesses in other pilot areas ({elsewhere.length})</summary>
          <ul className="business-grid">
            {elsewhere.map((b) => {
              const home = areas.get(b.area_id);
              return home ? <BusinessCard key={b.id} business={b} area={home} /> : null;
            })}
          </ul>
        </details>
      )}

      {programs.length > 0 && (
        <>
          <h3>Business support programs</h3>
          <ResourceList resources={programs} />
        </>
      )}
    </section>
  );
}

function BusinessCard({ business, area }: { business: Business; area: Area }) {
  const headingId = `business-${business.id}`;
  return (
    <li className="business" aria-labelledby={headingId}>
      <h3 id={headingId}>{business.name}</h3>
      <p className="business__meta">
        {business.category} · {business.address}
      </p>
      <p>{business.description}</p>
      <p className="business__why">
        <strong>Why it appears:</strong> {business.rationale}
      </p>
      <p className="area-context">
        <span className="area-context__label">Area context, not a business rating:</span> {area.label} commercial
        vulnerability {ratingText(area.commercial)}
      </p>
      <p className="business__actions">
        {business.website_url && (
          <a className="button" href={business.website_url} target="_blank" rel="noopener noreferrer">
            Visit website<span className="visually-hidden"> for {business.name}</span>
          </a>
        )}
        <a className="button button--quiet" href={directionsUrl(business)} target="_blank" rel="noopener noreferrer">
          Directions<span className="visually-hidden"> to {business.name}</span>
        </a>
      </p>
      <p className="business__source muted">
        Verified {formatDate(business.verified_at)} ·{' '}
        <a href={business.source_url} target="_blank" rel="noopener noreferrer">
          Listing source
        </a>
      </p>
    </li>
  );
}
