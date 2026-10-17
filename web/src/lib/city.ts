import type { Area, Geometry } from '../data/types';

export function shortArea(area: Area): string {
  return area.label.split(/[;,]/)[0]!.replace('Census Tract', 'Tract');
}

/** A representative map anchor; the highlighted polygon defines the assessment area. */
export function areaCenter(geometry: Geometry): [number, number] {
  const rings = geometry.type === 'Polygon' ? [geometry.coordinates[0] ?? []] : geometry.coordinates.map(p => p[0] ?? []);
  const points = rings.flat();
  if (!points.length) return [-118.353, 33.962];
  const xs = points.map(p => p[0]!);
  const ys = points.map(p => p[1]!);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}
