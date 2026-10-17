import { useEffect, useRef, useState } from 'react';
import type { Map as LibreMap, Marker as LibreMarker, GeoJSONSource } from 'maplibre-gl';
import type { Area, AssessmentKind, Business, Mode } from '../data/types';
import { areaCenter, shortArea } from '../lib/city';
import { lensColor, lensValue, rampColor, type Lens } from '../lib/outlook';
import 'maplibre-gl/dist/maplibre-gl.css';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';

interface Props {
  areas: Area[];
  businesses: Business[];
  mode: Mode;
  lens: Lens;
  kind: AssessmentKind;
  selectedId: string | null;
  selectedBusinessId: string | null;
  onSelect: (areaId: string, businessId?: string) => void;
}
const HOME = { center: [-118.353, 33.9615] as [number, number], zoom: 15.1, pitch: 52, bearing: -22 };

export function CityMap(props: Props) {
  const host = useRef<HTMLDivElement>(null);
  const mapRef = useRef<LibreMap | null>(null);
  const latest = useRef(props);
  latest.current = props;
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  const [flat, setFlat] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let disposed = false;
    let map: LibreMap | undefined;
    setReady(false);
    setFailed(false);
    const timer = window.setTimeout(() => { if (!disposed) setFailed(true); }, 18000);
    void import('maplibre-gl').then(({ Map, NavigationControl, AttributionControl, setWorkerUrl }) => {
      if (disposed || !host.current) return;
      try {
        // Vite must bundle the module worker and its imports, rather than resolve it beside the optimized library.
        setWorkerUrl(workerUrl);
        map = new Map({ container: host.current, style: 'https://tiles.openfreemap.org/styles/positron',
          ...HOME, maxPitch: 65, attributionControl: false });
        mapRef.current = map;
        map.addControl(new NavigationControl({ visualizePitch: true }), 'bottom-right');
        map.addControl(new AttributionControl({ compact: true }), 'bottom-left');
        map.on('pitchend', () => { if (!disposed) setFlat(map!.getPitch() < 10); });
        map.on('load', () => {
          if (disposed || !map) return;
          const label = map.getStyle().layers.find(layer => layer.type === 'symbol')?.id;
          map.addLayer({ id: 'city-buildings', type: 'fill-extrusion', source: 'openmaptiles',
            'source-layer': 'building', minzoom: 13,
            paint: { 'fill-extrusion-color': '#dadbd4',
              'fill-extrusion-height': ['coalesce', ['get', 'render_height'], 3],
              'fill-extrusion-base': ['coalesce', ['get', 'render_min_height'], 0],
              'fill-extrusion-opacity': 0.9 } }, label);
          // Every tract is filled by the active lens (outlook or today) so priority areas stand out at a glance.
          map.addSource('area-lens', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
          map.addLayer({ id: 'area-lens-fill', type: 'fill', source: 'area-lens', paint: { 'fill-color': ['get', 'color'], 'fill-opacity': 0.42 } }, 'city-buildings');
          map.addLayer({ id: 'area-lens-line', type: 'line', source: 'area-lens', paint: { 'line-color': '#ffffff', 'line-width': 1, 'line-opacity': 0.8 } });
          map.on('click', 'area-lens-fill', (event) => {
            // Marker clicks bubble through the map; let the marker's own selection win.
            if ((event.originalEvent.target as HTMLElement | null)?.closest?.('.city-marker')) return;
            const id = event.features?.[0]?.properties?.id;
            if (typeof id === 'string') latest.current.onSelect(id);
          });
          map.on('mouseenter', 'area-lens-fill', () => { map!.getCanvas().style.cursor = 'pointer'; });
          map.on('mouseleave', 'area-lens-fill', () => { map!.getCanvas().style.cursor = ''; });
          map.addSource('selected-area', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } });
          map.addLayer({ id: 'selected-area-fill', type: 'fill', source: 'selected-area', paint: { 'fill-color': '#46766b', 'fill-opacity': 0.065 } }, 'city-buildings');
          map.addLayer({ id: 'selected-area-line', type: 'line', source: 'selected-area', paint: { 'line-color': '#397965', 'line-width': 2, 'line-dasharray': [3, 2] } });
          window.clearTimeout(timer);
          setFailed(false);
          setReady(true);
        });
        map.on('error', () => {
          // Keep usable tiles after an isolated request fails; the startup timer handles an unavailable basemap.
          if (map?.loaded()) window.clearTimeout(timer);
        });
      } catch { window.clearTimeout(timer); setFailed(true); }
    }).catch(() => { if (!disposed) { window.clearTimeout(timer); setFailed(true); } });
    return () => { disposed = true; window.clearTimeout(timer); map?.remove(); mapRef.current = null; };
  }, [retry]);

  useEffect(() => {
    if (!ready || !mapRef.current) return;
    const map = mapRef.current;
    let disposed = false;
    const markers: LibreMarker[] = [];
    void import('maplibre-gl').then(({ Marker }) => {
      if (disposed) return;
      const locations = props.mode === 'business' && props.businesses.length > 0
        ? props.businesses.map(b => ({ id: b.area_id, businessId: b.id, label: b.name, badge: b.outlook ? String(Math.round(b.outlook.priority_score)) : undefined,
            coordinates: [b.location.lon, b.location.lat] as [number, number], color: b.outlook ? rampColor(b.outlook.priority_score / 100) : '#397965' }))
        : props.areas.map(a => ({ id: a.id, businessId: undefined, label: shortArea(a), badge: undefined, coordinates: areaCenter(a.boundary), color: lensColor(a, props.lens, props.kind) }));
      for (const item of locations) {
        const button = document.createElement('button');
        button.type = 'button';
        const selected = item.businessId ? item.businessId === props.selectedBusinessId : item.id === props.selectedId;
        button.className = `city-marker${selected ? ' is-active' : ''}`;
        button.style.setProperty('--marker-color', item.color);
        button.setAttribute('aria-label', `Explore ${item.label}`);
        button.setAttribute('aria-pressed', String(selected));
        const dot = document.createElement('span'); dot.className = 'city-marker-dot';
        const label = document.createElement('span'); label.className = 'city-marker-label'; label.textContent = item.label;
        if (item.badge) {
          // Visible score only; the accessible name stays the business name.
          const badge = document.createElement('span'); badge.className = 'city-marker-badge'; badge.textContent = item.badge;
          badge.setAttribute('aria-hidden', 'true'); label.append(badge);
        }
        button.append(dot, label);
        button.addEventListener('click', () => latest.current.onSelect(item.id, item.businessId));
        markers.push(new Marker({ element: button, anchor: 'center' }).setLngLat(item.coordinates).addTo(map));
      }
    });
    return () => { disposed = true; markers.forEach(m => m.remove()); };
  }, [ready, props.areas, props.businesses, props.mode, props.lens, props.kind, props.selectedId, props.selectedBusinessId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    (map.getSource('area-lens') as GeoJSONSource).setData({ type: 'FeatureCollection', features: props.areas.map(a => ({
      type: 'Feature', geometry: a.boundary,
      properties: { id: a.id, color: lensColor(a, props.lens, props.kind), value: lensValue(a, props.lens, props.kind) } })) });
  }, [ready, props.areas, props.lens, props.kind]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const area = props.areas.find(a => a.id === props.selectedId);
    (map.getSource('selected-area') as GeoJSONSource).setData({ type: 'FeatureCollection', features: area ? [{ type: 'Feature', properties: {}, geometry: area.boundary }] : [] });
    if (!area) return;
    const business = props.businesses.find(b => b.id === props.selectedBusinessId);
    const center: [number, number] = business ? [business.location.lon, business.location.lat] : areaCenter(area.boundary);
    map.easeTo({ center, zoom: business ? 16 : 14.6, duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 800,
      offset: window.innerWidth > 760 ? [-170, 0] : [0, -100] });
  }, [ready, props.selectedId, props.selectedBusinessId, props.areas, props.businesses]);

  return <>
    <div ref={host} className="city-canvas" aria-label="Interactive city map" />
    {!ready && !failed && <div className="map-message" role="status">Opening Inglewood…</div>}
    {failed && <div className="map-message map-message--error" role="status"><strong>City map unavailable</strong><p>You can still search and explore places using the list.</p><button onClick={() => setRetry(n => n + 1)}>Retry map</button></div>}
    <div className="city-view-controls" aria-label="Map view controls">
      <button disabled={!ready} aria-pressed={!flat} onClick={() => mapRef.current?.easeTo({ pitch: flat ? 52 : 0, bearing: flat ? -22 : 0, duration: 450 })}>{flat ? '3D view' : '2D view'}</button>
      <button disabled={!ready} onClick={() => mapRef.current?.easeTo({ ...HOME, duration: 700, offset: [0, 0] })} aria-label="Reset map to Inglewood">↗ <span>Reset view</span></button>
    </div>
  </>;
}
