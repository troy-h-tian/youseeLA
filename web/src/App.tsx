import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { AreaList } from './components/AreaList';
import { AreaMap } from './components/AreaMap';
import { AssessmentPanel } from './components/AssessmentPanel';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { HistoricalComparison } from './components/HistoricalComparison';
import { ModeSwitch } from './components/ModeSwitch';
import { BundleError, loadBundle } from './data/load';
import type { DataSource } from './data/load';
import { ASSESSMENT_FOR_MODE } from './data/types';
import type { Bundle, Mode } from './data/types';
import { BusinessPanel } from './features/business/BusinessPanel';
import { HousingPanel } from './features/housing/HousingPanel';
import { formatDate } from './lib/format';
import { finishPendingActions, markInitialRender, startAction } from './lib/perf';
import { useContextView } from './lib/context';
import { rankAreas } from './lib/ranking';

type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string; problems: string[] }
  | { status: 'ready'; bundle: Bundle };

interface AppProps {
  source: DataSource;
  fetchImpl?: typeof fetch;
}

export function App({ source, fetchImpl }: AppProps) {
  const [state, setState] = useState<LoadState>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    loadBundle(source, fetchImpl)
      .then((bundle) => !cancelled && setState({ status: 'ready', bundle }))
      .catch((error: unknown) => {
        if (cancelled) return;
        setState({
          status: 'error',
          message: error instanceof Error ? error.message : String(error),
          problems: error instanceof BundleError ? error.problems : [],
        });
      });
    return () => {
      cancelled = true;
    };
  }, [source, fetchImpl]);

  if (state.status === 'loading') {
    return (
      <Shell>
        <p className="state" role="status">
          Loading area data…
        </p>
      </Shell>
    );
  }
  if (state.status === 'error') {
    return (
      <Shell>
        <div className="state state--error" role="alert">
          <h2>The area data could not be loaded</h2>
          <p>{state.message}</p>
          {state.problems.length > 0 && (
            <ul>
              {state.problems.slice(0, 20).map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          {source === 'demo' && (
            <p>
              For development, <a href="?data=fixture">open the labeled demo fixture</a> instead.
            </p>
          )}
        </div>
      </Shell>
    );
  }
  return <Explorer bundle={state.bundle} />;
}

function Shell({ children, banner }: { children: ReactNode; banner?: ReactNode }) {
  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar__inner">
          <h1 className="brand">
            youseeLA <span className="brand__sub">Inglewood area explorer</span>
          </h1>
        </div>
        {banner}
      </header>
      {children}
    </div>
  );
}

function DataBanner({ bundle }: { bundle: Bundle }) {
  if (bundle.methodology.visual_method === 'clip_pairs') return <p className="data-banner" role="note">
    <strong>Historical multimodal prototype · as of {bundle.methodology.assessed_as_of}.</strong> ACS 2010–2014 versus 2015–2019; photos from 2019–2020. Experimental CLIP score, not a current risk prediction.
  </p>;
  if (bundle.data_kind === 'fixture') {
    return (
      <p className="data-banner data-banner--fixture" role="note">
        <strong>Demo fixture.</strong> Invented places, businesses and scores for development — not real Inglewood
        data.
      </p>
    );
  }
  return (
    <p className="data-banner" role="note">
      <strong>Experimental assessment.</strong> Generated {formatDate(bundle.generated_at)} · rubric{' '}
      {bundle.methodology.config_version}
    </p>
  );
}

export function Explorer({ bundle }: { bundle: Bundle }) {
  const [mode, setMode] = useState<Mode>('business');
  const [selectedId, setSelectedId] = useState<string | null>(
    () => rankAreas(bundle.areas, 'commercial').rated[0]?.id ?? bundle.areas.find(a => a.id === bundle.businesses[0]?.area_id)?.id ?? bundle.areas[0]?.id ?? null,
  );
  const [compareId, setCompareId] = useState<string | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const kind = ASSESSMENT_FOR_MODE[mode];
  const areaById = useMemo(() => new Map(bundle.areas.map((a) => [a.id, a] as const)), [bundle.areas]);
  const area = selectedId ? areaById.get(selectedId) ?? null : null;

  useEffect(() => {
    markInitialRender();
  }, []);
  useEffect(() => {
    finishPendingActions();
  });

  const changeMode = useCallback((next: Mode) => {
    startAction('mode-switch');
    setMode(next);
  }, []);
  const selectArea = useCallback((id: string) => {
    startAction('area-select');
    setSelectedId(id);
  }, []);
  const closeEvidence = useCallback(() => setEvidenceOpen(false), []);

  return (
    <Shell banner={<DataBanner bundle={bundle} />}>
      <div className="mode-bar">
        <div className="dataset-links"><a href="?data=demo">Current Census explorer</a><a href="?data=clip">Historical CLIP assessment</a></div>
        <ModeSwitch mode={mode} onChange={changeMode} panelId="mode-panel" />
        {bundle.data_kind === 'real' && <a className="historical-jump" href="#historical-comparison">Explore a historical photo comparison →</a>}
      </div>
      {useContextView(bundle.areas, kind) && <section className="evidence-intro">
        <h2>Available neighborhood data</h2>
        <p>Explore Census housing conditions, verified local businesses and a dated photo comparison.
          Combined assessments are pending; the percentages below are direct measurements, not risk predictions.</p>
      </section>}
      {bundle.areas.length === 0 ? (
        <main className="state">
          <p>This bundle contains no areas yet.</p>
        </main>
      ) : (
        <main className="layout" id="mode-panel" role="tabpanel" aria-labelledby={`tab-${mode}`}>
          <aside className="sidebar">
            <AreaMap
              areas={bundle.areas}
              kind={kind}
              selectedId={selectedId}
              compareId={mode === 'housing' ? compareId : null}
              onSelect={selectArea}
            />
            <AreaList areas={bundle.areas} kind={kind} selectedId={selectedId} onSelect={selectArea} />
          </aside>
          <div className="detail">
            {area ? (
              <>
                <AssessmentPanel
                  area={area}
                  kind={kind}
                  methodology={bundle.methodology}
                  onOpenEvidence={() => setEvidenceOpen(true)}
                />
                {mode === 'business' ? (
                  <BusinessPanel bundle={bundle} area={area} />
                ) : (
                  <HousingPanel bundle={bundle} area={area} compareId={compareId} onCompareChange={setCompareId} />
                )}
              </>
            ) : (
              <p className="state">Select an area to see its assessment.</p>
            )}
          </div>
        </main>
      )}
      {bundle.data_kind === 'real' && <HistoricalComparison />}
      <footer className="footer">
        <h2>About these assessments</h2>
        <p>{bundle.methodology.summary}</p>
        <ul>
          {bundle.methodology.limitations.map((l) => (
            <li key={l}>{l}</li>
          ))}
        </ul>
      </footer>
      {area && (
        <EvidenceDrawer open={evidenceOpen} onClose={closeEvidence} area={area} kind={kind} evidence={bundle.evidence} />
      )}
    </Shell>
  );
}
