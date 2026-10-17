/**
 * User-timing marks for the browser scalability evaluation.
 *
 * Definition: an action measure runs from the input handler (start mark) to
 * the first macrotask after the next animation frame following React's commit,
 * which approximates "updated content has been painted". Initial render runs
 * from navigation start to the first committed paint of a loaded bundle.
 * Measures are named `youseela:<action>` and read by tests/scalability.spec.ts.
 */

const pending = new Set<string>();
const PREFIX = 'youseela:';

export type PerfAction = 'mode-switch' | 'area-select';

export function startAction(action: PerfAction): void {
  if (typeof performance === 'undefined' || typeof performance.mark !== 'function') return;
  performance.mark(`${PREFIX}${action}:start`);
  pending.add(action);
}

function afterPaint(callback: () => void): void {
  if (typeof requestAnimationFrame !== 'function') return;
  requestAnimationFrame(() => setTimeout(callback, 0));
}

/** Call from an effect after the content affected by pending actions commits. */
export function finishPendingActions(): void {
  if (pending.size === 0) return;
  const actions = [...pending];
  pending.clear();
  afterPaint(() => {
    for (const action of actions) {
      performance.mark(`${PREFIX}${action}:end`);
      performance.measure(`${PREFIX}${action}`, `${PREFIX}${action}:start`, `${PREFIX}${action}:end`);
    }
  });
}

let initialMeasured = false;

export function markInitialRender(): void {
  if (initialMeasured || typeof performance === 'undefined' || typeof performance.mark !== 'function') return;
  initialMeasured = true;
  afterPaint(() => {
    performance.mark(`${PREFIX}initial-render:end`);
    performance.measure(`${PREFIX}initial-render`, { start: 0, end: `${PREFIX}initial-render:end` });
  });
}
