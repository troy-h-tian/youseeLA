import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { Bundle, Mode } from '../data/types';
import { ASSESSMENT_FOR_MODE } from '../data/types';
import { CityMap } from './CityMap';
import { BusinessPhoto } from './BusinessPhoto';
import { ModeSwitch } from './ModeSwitch';
import { AssessmentPanel } from './AssessmentPanel';
import { AreaStory } from './AreaStory';
import { NextSteps } from './NextSteps';
import { NeighborhoodSummary } from './NeighborhoodSummary';
import { OutlookCard } from './OutlookCard';
import { rampColor, UNRATED_COLOR, type Lens } from '../lib/outlook';
import { NumericalContext } from './NumericalContext';
import { EvidenceDrawer } from './EvidenceDrawer';
import { HistoricalComparison } from './HistoricalComparison';
import { BusinessPanel } from '../features/business/BusinessPanel';
import { HousingPanel } from '../features/housing/HousingPanel';
import { shortArea } from '../lib/city';
import { finishPendingActions, markInitialRender, startAction } from '../lib/perf';
import '../city.css';

type DetailTab = 'overview' | 'assessment' | 'support';

export function CityExplorer({ bundle }: { bundle: Bundle }) {
  const [mode, setMode] = useState<Mode>('business');
  const [lens, setLens] = useState<Lens>('outlook');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [businessId, setBusinessId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [browsing, setBrowsing] = useState(false);
  const [tab, setTab] = useState<DetailTab>('overview');
  const [compareId, setCompareId] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [photosOpen, setPhotosOpen] = useState(false);
  const photoDialog = useRef<HTMLDialogElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const panelRef = useRef<HTMLElement>(null);
  const area = bundle.areas.find(a => a.id === selectedId);
  const business = bundle.businesses.find(b => b.id === businessId);
  const kind = ASSESSMENT_FOR_MODE[mode];
  const businessMarkers = mode === 'business' && bundle.businesses.length > 0;
  const historical = bundle.methodology.visual_method === 'clip_pairs';
  const fixture = bundle.data_kind === 'fixture';
  const results = useMemo(() => {
    const term = query.trim().toLowerCase();
    const businesses = mode === 'business' ? bundle.businesses.filter(b => `${b.name} ${b.address} ${b.category}`.toLowerCase().includes(term)) : [];
    const areas = bundle.areas.filter(a => `${a.label} ${a.id}`.toLowerCase().includes(term));
    return { businesses, areas };
  }, [bundle, mode, query]);
  const selectArea = useCallback((id: string, selectedBusiness?: string) => {
    startAction('area-select');
    setSelectedId(id); setBusinessId(selectedBusiness ?? null); setTab('overview'); setBrowsing(false); setQuery('');
    // Move keyboard focus into the details after React has mounted the panel.
    window.requestAnimationFrame(() => panelRef.current?.focus());
  }, []);
  const changeMode = (next: Mode) => {
    startAction('mode-switch'); setMode(next); setBusinessId(null); setTab('overview');
  };
  const closeDetails = () => { setSelectedId(null); setBusinessId(null); searchRef.current?.focus(); setBrowsing(false); };
  useEffect(() => { markInitialRender(); }, []);
  useEffect(() => { finishPendingActions(); });
  useEffect(() => {
    if (photosOpen) photoDialog.current?.showModal();
    else photoDialog.current?.close();
  }, [photosOpen]);
  const showResults = browsing || query.length > 0;

  return <main className="city-explorer">
    <CityMap areas={bundle.areas} businesses={bundle.businesses} mode={mode} lens={lens} kind={kind} selectedId={selectedId} selectedBusinessId={businessId} onSelect={selectArea} />
    <header className="city-header">
      <a className="city-brand" href="?data=demo" aria-label="youseeLA home"><span className="brand-symbol" aria-hidden="true">y.</span><span>yousee<span className="brand-la">LA</span><small>A closer look at your city.</small></span></a>
      <div className="city-location"><span className="location-dot" /> INGLEWOOD, CA</div>
      <button className="photo-button" onClick={() => setPhotosOpen(true)}>Street stories <span aria-hidden="true">↗</span></button>
    </header>

    <section className="explore-tools" aria-label="Find a place">
      <nav className="dataset-switch" aria-label="Explore views">
        <a href="?data=demo" aria-current={!historical && !fixture ? 'page' : undefined}>Explore today</a>
        <a href="?data=clip" aria-current={historical ? 'page' : undefined}>Historical analysis</a>
      </nav>
      <div className="city-search"><span aria-hidden="true">⌕</span><input ref={searchRef} type="search" aria-label="Search places or Census tracts" placeholder={mode === 'business' ? 'Find a local place…' : 'Find a Census tract…'} value={query} onFocus={() => setBrowsing(true)} onChange={e => setQuery(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') { setBrowsing(false); setQuery(''); e.currentTarget.blur(); } }} /><button aria-label={showResults ? 'Close place list' : 'Browse all places'} onClick={() => { setBrowsing(!showResults); setQuery(''); }}>{showResults ? '×' : '☷'}</button></div>
      <ModeSwitch mode={mode} onChange={changeMode} panelId="city-mode-panel" />
      {showResults && <nav className="city-results" aria-label="Places and areas">
        <div className="results-heading">{query ? 'SEARCH RESULTS' : 'EXPLORE INGLEWOOD'}<span>{results.businesses.length + results.areas.length} places</span></div>
        {results.businesses.map(b => <button key={b.id} className="place-result" onClick={() => selectArea(b.area_id, b.id)}><span className="result-icon" aria-hidden="true">↗</span><span><strong>{b.name}</strong><small>{b.address}</small></span><span aria-hidden="true">→</span></button>)}
        {results.areas.length > 0 && <p className="results-subheading">CENSUS TRACTS · AREA CONTEXT</p>}
        {results.areas.map(a => <button key={a.id} className="place-result" aria-pressed={a.id === selectedId} onClick={() => selectArea(a.id)}><span className="result-icon result-icon--area" aria-hidden="true">◇</span><span><strong>{shortArea(a)}</strong><small>{a.id} · {a[kind].status === 'rated' ? 'Experimental assessment' : 'Census context'}</small></span><span aria-hidden="true">→</span></button>)}
        {!results.areas.length && !results.businesses.length && <p className="no-results">No matching places. Try a business name or tract number.</p>}
      </nav>}
    </section>

    <div className={`city-dataset-note${fixture || historical ? ' is-experimental' : ''}`} role="note">
      {fixture ? 'Synthetic demo · invented places and scores' : historical ? `Historical multimodal prototype · as of ${bundle.methodology.assessed_as_of}` : 'Real places. Census context. An evolving picture.'}
      {historical && <span>Historical photos and experimental scores · not current risk.</span>}
    </div>

    <div id="city-mode-panel" role="tabpanel" aria-labelledby={`tab-${mode}`}>
      {!area && !showResults && <section className="city-intro">
        <p className="city-eyebrow">THE CITY, A LITTLE CLOSER</p>
        <h1>{historical ? <>Neighborhoods,<br />through time.</> : <>Every block<br />has a story.</>}</h1>
        <p>{bundle.areas.length === 0 ? 'This bundle contains no areas yet.' : historical ? 'Census data and dated photos. Experimental scores, not current risk.' : mode === 'business' ? 'Discover local places and the neighborhoods around them.' : 'Explore housing conditions, one neighborhood at a time.'}</p>
        {historical && <div className="historical-examples" aria-label="Scored historical examples">
          {(['business', 'housing'] as const).flatMap(exampleMode => {
            // Showcase image-backed scores first; Census-only rough scores are the fallback.
            const rated = (item: typeof bundle.areas[number]) => item[ASSESSMENT_FOR_MODE[exampleMode]].status === 'rated';
            const example = bundle.areas.find(item => rated(item) && !item[ASSESSMENT_FOR_MODE[exampleMode]].basis?.startsWith('Rough'))
              ?? bundle.areas.find(rated);
            return example ? [<button key={exampleMode} onClick={() => { changeMode(exampleMode); selectArea(example.id); }}>
              <span>{exampleMode === 'business' ? 'Commercial' : 'Housing'} example<small>{shortArea(example)}</small></span><span aria-hidden="true">↗</span>
            </button>] : [];
          })}
        </div>}
        <button className="explore-cta" onClick={() => { setBrowsing(true); searchRef.current?.focus(); }}>{historical ? 'Browse historical areas' : `Explore ${mode === 'business' ? 'local places' : 'neighborhoods'}`} <span>↗</span></button>
      </section>}
      {area && <section ref={panelRef} tabIndex={-1} className="location-panel" aria-label="Location details">
        <header className="location-panel-header"><div><p className="city-eyebrow">{business ? business.category : 'NEIGHBORHOOD CONTEXT'}</p><h2>{business?.name ?? shortArea(area)}</h2><p>{business?.address ?? `Inglewood area · ${area.id}`}</p></div><button className="close-location" aria-label="Close location details" onClick={closeDetails}>×</button></header>
        <div className="detail-tabs" role="tablist" aria-label="Location information" onKeyDown={event => {
          const tabs: DetailTab[] = ['overview', 'assessment', 'support'];
          if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? 2 : (tabs.indexOf(tab) + (event.key === 'ArrowRight' ? 1 : 2)) % 3;
          setTab(tabs[next]!);
          document.getElementById(`detail-tab-${tabs[next]}`)?.focus();
        }}>{(['overview', 'assessment', 'support'] as const).map(t => <button key={t} id={`detail-tab-${t}`} role="tab" tabIndex={tab === t ? 0 : -1} aria-selected={tab === t} aria-controls="location-content" onClick={() => setTab(t)}>{t === 'assessment' ? 'Evidence' : t === 'support' ? 'Local support' : 'Overview'}</button>)}</div>
        <div key={`${selectedId}-${businessId}-${tab}`} className="location-content" id="location-content" role="tabpanel" aria-labelledby={`detail-tab-${tab}`}>
          {tab === 'overview' && <>
            {business && <><BusinessPhoto businessId={business.id} name={business.name} /><p className="place-description">{business.description}</p><a className="listing-source" href={business.source_url} target="_blank" rel="noopener noreferrer">Listing source · verified {business.verified_at}</a></>}
            <div className="tract-label"><span>◇</span><div><strong>{shortArea(area)}</strong><small>Outlined on the map · area context, not a business rating</small></div></div>
            <AreaStory area={area} kind={kind} onEvidence={() => setEvidenceOpen(true)} />
            <NextSteps area={area} bundle={bundle} mode={mode} business={business} onBusiness={item => selectArea(item.area_id, item.id)} onSupport={() => setTab('support')} />
            <NumericalContext area={area} />
            <OutlookCard area={area} mode={mode} />
            <p className="assessment-status"><span className="location-dot" />{area[kind].status === 'rated' ? `Today’s pressure score: ${area[kind].score?.toFixed(1)} / 100${area[kind].score_range ? ` · range ${area[kind].score_range!.lower.toFixed(0)}–${area[kind].score_range!.upper.toFixed(0)}` : ''}` : 'Pressure score unavailable'}<small>{area[kind].status === 'rated' ? (area[kind].basis ?? 'An exploratory index, not a probability. See Evidence for limitations.') : 'Available housing facts are shown above. Missing evidence is not low risk.'}</small></p>
            {area[kind].status !== 'rated' && <div className="missing-summary">
              <h3>Why there’s no score yet</h3>
              <p>{area[kind].unrated_reason ?? 'There is not enough compatible evidence to calculate an assessment.'}</p>
            </div>}
            <button className="panel-link" onClick={() => setTab('assessment')}>Explore the evidence <span>→</span></button>
            <NeighborhoodSummary area={area} kind={kind} onSources={() => setEvidenceOpen(true)} />
          </>}
          {tab === 'assessment' && <><AssessmentPanel area={area} kind={kind} methodology={bundle.methodology} onOpenEvidence={() => setEvidenceOpen(true)} /><details className="model-status"><summary>About this dataset</summary><p>{bundle.methodology.summary}</p><ul>{bundle.methodology.limitations.map(item => <li key={item}>{item}</li>)}</ul></details></>}
          {tab === 'support' && (mode === 'housing' ? <HousingPanel bundle={bundle} area={area} compareId={compareId} onCompareChange={setCompareId} /> : <BusinessPanel bundle={bundle} area={area} />)}
        </div>
      </section>}
    </div>

    <footer className="city-footer"><div className="city-legend">
      {businessMarkers && <span className="legend-business"><span className="legend-dot legend-dot--business" />Local business · not a risk rating</span>}
      <span className="lens-legend" aria-label="Map color key">
        <span className="lens-switch" role="group" aria-label="Color the map by">
          <button aria-pressed={lens === 'outlook'} onClick={() => setLens('outlook')}>{historical ? 'Model backtest' : '5-year outlook'}</button>
          <button aria-pressed={lens === 'today'} onClick={() => setLens('today')}>Today’s score</button>
        </span>
        <span className="lens-key">
          <strong>{lens === 'outlook' ? (historical ? 'Predicted in 2019: rent pressure' : 'Predicted rent pressure, next 5 years') : 'Today’s pressure score'}</strong>
          <span className="lens-scale"><span>Lower</span><span className="lens-ramp" style={{ background: `linear-gradient(90deg, ${rampColor(0)}, ${rampColor(.5)}, ${rampColor(.75)}, ${rampColor(1)})` }} aria-hidden="true" /><span>{lens === 'outlook' ? 'Top of LA County' : 'Higher'}</span>
            <span className="lens-none"><span className="legend-swatch" style={{ background: UNRATED_COLOR }} />No score</span></span>
        </span>
      </span>
    </div></footer>
    {area && <EvidenceDrawer open={evidenceOpen} onClose={() => setEvidenceOpen(false)} area={area} kind={kind} evidence={bundle.evidence} />}
    <dialog ref={photoDialog} className="street-dialog" onCancel={() => setPhotosOpen(false)} onClose={() => setPhotosOpen(false)} aria-label="Historical street stories"><button className="street-close" onClick={() => setPhotosOpen(false)}>Close stories ×</button>{photosOpen && <HistoricalComparison />}</dialog>
  </main>;
}
