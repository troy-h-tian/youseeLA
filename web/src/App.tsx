import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { BundleError, loadBundle } from './data/load';
import type { DataSource } from './data/load';
import type { Bundle } from './data/types';
import { CityExplorer as Explorer } from './components/CityExplorer';
export { CityExplorer as Explorer } from './components/CityExplorer';

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
