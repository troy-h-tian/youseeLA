import type { Resource } from '../data/types';
import { formatDate } from '../lib/format';

/** Resources of one kind that serve the area; area_ids null means every pilot area. */
export function applicableResources(resources: Resource[], kind: Resource['kind'], areaId: string): Resource[] {
  return resources.filter((r) => r.kind === kind && (r.area_ids === null || r.area_ids.includes(areaId)));
}

export function ResourceList({ resources }: { resources: Resource[] }) {
  return (
    <ul className="resources">
      {resources.map((r) => (
        <li key={r.id} className="resource">
          <a href={r.url} target="_blank" rel="noopener noreferrer">
            {r.name}
          </a>
          <span>{r.description}</span>
          <span className="muted">
            Serves: {r.service_area} · Verified {formatDate(r.verified_at)}
          </span>
        </li>
      ))}
    </ul>
  );
}
