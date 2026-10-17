import type { Area, Business, Bundle, Mode } from '../data/types';
import { applicableResources } from './ResourceList';
import { directionsUrl, formatDate } from '../lib/format';

export function NextSteps({ area, bundle, mode, business, onBusiness, onSupport }: {
  area: Area; bundle: Bundle; mode: Mode; business?: Business;
  onBusiness: (business: Business) => void; onSupport: () => void;
}) {
  const historical = bundle.methodology.visual_method === 'clip_pairs';
  const businesses = bundle.businesses.filter(item => item.area_id === area.id);
  const resources = applicableResources(bundle.resources, mode, area.id);
  return <section className="next-steps" aria-label="What you can do">
    <h3>What you can do</h3>
    {historical ? <>
      <p>This view describes the past. Open today’s explorer for listed businesses and housing resources.</p>
      <a className="next-step" href="?data=demo">Explore today <span aria-hidden="true">↗</span></a>
    </> : mode === 'business' ? business ? <>
      <p>Explore this business directly. The area’s data does not describe its finances or likelihood of closing.</p>
      <div className="place-actions">
        {business.website_url && <a href={business.website_url} target="_blank" rel="noopener noreferrer">Visit website <span aria-hidden="true">↗</span></a>}
        <a href={directionsUrl(business)} target="_blank" rel="noopener noreferrer">Directions <span aria-hidden="true">↗</span></a>
      </div>
    </> : <>
      <p>{businesses.length ? 'Get to know a business listed in this tract.' : 'No businesses are listed in this tract yet. Local support includes listings elsewhere in the pilot area.'}</p>
      {businesses.slice(0, 2).map(item => <button className="next-step" key={item.id} onClick={() => onBusiness(item)}>
        <span>{item.name}<small>{item.category} · {item.address}</small></span><span aria-hidden="true">→</span>
      </button>)}
      <button className="panel-link" onClick={onSupport}>Explore local support <span aria-hidden="true">→</span></button>
    </> : <>
      <p>{resources.length ? 'These organizations list services for this area. Check current eligibility and availability with them.' : 'No housing resources are listed for this area yet.'}</p>
      {resources.slice(0, 2).map(resource => <a className="next-step" key={resource.id} href={resource.url} target="_blank" rel="noopener noreferrer">
        <span>{resource.name}<small>{resource.description}</small><small>Serves: {resource.service_area} · Listed as verified {formatDate(resource.verified_at)}</small></span><span aria-hidden="true">↗</span>
      </a>)}
      <button className="panel-link" onClick={onSupport}>View resources and compare areas <span aria-hidden="true">→</span></button>
    </>}
  </section>;
}
