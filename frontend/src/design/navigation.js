/**
 * Navigation and loading — Operator Console stillness.
 *
 * Motion confirms what changed. Loading does not get to invent a second page.
 * The chrome (header, page title, tabs, metric strip) stays put unless the
 * operator has actually left a product surface.
 *
 * Rules:
 *   1. A shell does not remount for params, tabs, or drill-downs.
 *      `/apps/12` and `/apps/12/envs/4` are the same shell.
 *   2. Stale-while-revalidate. Keep the last painted data on screen. Swap
 *      values when the response lands. Never blank a populated view.
 *   3. Defer loading chrome. If the fetch finishes before LOADING_DEFER_MS,
 *      show nothing — a 80ms progress bar is worse than no indicator.
 *   4. Full-page loading is cold-start only (no data to show yet).
 *   5. Tabs cut. They do not fade. Shell changes also cut. Fading a
 *      destination that is still loading paints a blank frame. No
 *      `mode="wait"` gap, no vertical nudge, no route opacity cycle.
 */

/** Hide refresh chrome that would exist for less than this. */
export const LOADING_DEFER_MS = 200;

/** Host notebooks only exist inside a wave. Returns null without a wave id. */
export const hostNotebookPath = (recordId, waveId) => {
  if (recordId == null || recordId === '' || waveId == null || waveId === '') return null;
  return `/pentest/record/${recordId}?wave=${waveId}`;
};

/**
 * Stable identity for a product surface. Route transitions key on this, not
 * the raw pathname, so drill-downs and doc pages do not tear the tree down.
 */
export const routeShellKey = (pathname = '') => {
  const path = String(pathname).split('?')[0].replace(/\/+$/, '') || '/';
  const parts = path.split('/').filter(Boolean);
  const root = parts[0] || '';

  if (root === 'apps' && parts[1]) {
    if (parts[2] === 'waves' && parts[4] === 'scan-live') return `apps/${parts[1]}/scan-live`;
    return `apps/${parts[1]}`;
  }
  if (root === 'docs') return 'docs';
  if (root === 'pentest' && parts[1] === 'record' && parts[2]) {
    if (parts[3] === 'scan-live') return `pentest/record/${parts[2]}/scan-live`;
    return `pentest/record/${parts[2]}`;
  }
  if (root === 'records' && parts.length >= 2) {
    const id = parts[1] === 'record' ? parts[2] : parts[1];
    return id ? `records/${id}` : 'records';
  }
  return path;
};
