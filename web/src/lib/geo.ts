import type { Geometry } from '../data/types';

export interface Projection {
  width: number;
  height: number;
  project: (lon: number, lat: number) => [number, number];
}

function rings(geometry: Geometry): number[][][] {
  return geometry.type === 'Polygon' ? geometry.coordinates : geometry.coordinates.flat();
}

/**
 * Equirectangular projection scaled by cos(mid-latitude). Accurate enough for a
 * few tracts in one city, and avoids a mapping dependency or tile basemap.
 */
export function fitProjection(geometries: Geometry[], width: number, padding = 8): Projection {
  let minLon = Infinity;
  let maxLon = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  for (const geometry of geometries) {
    for (const ring of rings(geometry)) {
      for (const [lon, lat] of ring) {
        if (lon === undefined || lat === undefined) continue;
        minLon = Math.min(minLon, lon);
        maxLon = Math.max(maxLon, lon);
        minLat = Math.min(minLat, lat);
        maxLat = Math.max(maxLat, lat);
      }
    }
  }
  if (!Number.isFinite(minLon)) {
    return { width, height: width / 2, project: () => [width / 2, width / 4] };
  }
  const kx = Math.cos(((minLat + maxLat) / 2) * (Math.PI / 180));
  const spanX = Math.max((maxLon - minLon) * kx, 1e-9);
  const spanY = Math.max(maxLat - minLat, 1e-9);
  const scale = (width - padding * 2) / spanX;
  const height = Math.max(spanY * scale + padding * 2, 80);
  const offsetY = (height - spanY * scale) / 2;
  return {
    width,
    height,
    project: (lon, lat) => [padding + (lon - minLon) * kx * scale, offsetY + (maxLat - lat) * scale],
  };
}

export function pathData(geometry: Geometry, projection: Projection): string {
  return rings(geometry)
    .map(
      (ring) =>
        ring
          .map(([lon, lat], i) => {
            const [x, y] = projection.project(lon ?? 0, lat ?? 0);
            return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`;
          })
          .join('') + 'Z',
    )
    .join('');
}

/** Vertex average of the outer ring(s); good enough to place a short label. */
export function labelPoint(geometry: Geometry, projection: Projection): [number, number] {
  const outer = geometry.type === 'Polygon' ? [geometry.coordinates[0] ?? []] : geometry.coordinates.map((p) => p[0] ?? []);
  let x = 0;
  let y = 0;
  let n = 0;
  for (const ring of outer) {
    for (const [lon, lat] of ring) {
      const [px, py] = projection.project(lon ?? 0, lat ?? 0);
      x += px;
      y += py;
      n += 1;
    }
  }
  return n === 0 ? [0, 0] : [x / n, y / n];
}
