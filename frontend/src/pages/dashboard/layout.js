import { TREND_WINDOWS } from './constants';

export const WIDGET_IDS = ['trend', 'severity', 'coverage', 'apps', 'workload', 'recent'];

export const DEFAULT_LAYOUT = {
  order: ['trend', 'severity', 'coverage', 'apps', 'workload', 'recent'],
  spans: {
    trend: 'full',
    severity: 'half',
    coverage: 'half',
    apps: 'half',
    workload: 'half',
    recent: 'full'
  }
};

export const DEFAULT_TREND_WINDOW = '12w';

export const layoutStorageKey = (username) => `raptor.dashboard.layout.${username || 'anon'}`;

const sanitizeLayout = (raw) => {
  if (!raw || typeof raw !== 'object') return { ...DEFAULT_LAYOUT, spans: { ...DEFAULT_LAYOUT.spans } };
  const seen = new Set();
  const order = [];
  const incoming = Array.isArray(raw.order) ? raw.order : DEFAULT_LAYOUT.order;
  incoming.forEach((id) => {
    if (WIDGET_IDS.includes(id) && !seen.has(id)) {
      seen.add(id);
      order.push(id);
    }
  });
  WIDGET_IDS.forEach((id) => {
    if (!seen.has(id)) order.push(id);
  });
  const spans = { ...DEFAULT_LAYOUT.spans };
  WIDGET_IDS.forEach((id) => {
    const value = raw.spans?.[id];
    spans[id] = value === 'full' || value === 'half' ? value : DEFAULT_LAYOUT.spans[id];
  });
  return { order, spans };
};

export const loadLayout = (username) => {
  if (typeof window === 'undefined' || !window.localStorage) {
    return sanitizeLayout(DEFAULT_LAYOUT);
  }
  try {
    const raw = window.localStorage.getItem(layoutStorageKey(username));
    return sanitizeLayout(raw ? JSON.parse(raw) : DEFAULT_LAYOUT);
  } catch (error) {
    return sanitizeLayout(DEFAULT_LAYOUT);
  }
};

export const saveLayout = (username, layout) => {
  if (typeof window === 'undefined' || !window.localStorage) return;
  try {
    window.localStorage.setItem(layoutStorageKey(username), JSON.stringify(sanitizeLayout(layout)));
  } catch (error) {
    // Quota or private-mode failures should not break the page.
  }
};

export const sliceWeekly = (weekly = [], windowKey = DEFAULT_TREND_WINDOW) => {
  const count = TREND_WINDOWS[windowKey] || TREND_WINDOWS['12w'];
  return weekly.slice(-count);
};
