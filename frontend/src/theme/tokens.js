/**
 * Compatibility accessors for screens that have not yet been rewritten onto
 * the Operator Console primitives. Signatures are unchanged; the colours
 * come from `design/tokens.js`.
 */

import {
  SEVERITY_TIERS,
  STATUS_VOCABULARY,
  getPalette,
  isEmphasisedEnv
} from '../design/tokens';

export { SEVERITY_TIERS };

const paletteFor = (mode) => getPalette(mode === 'light' ? 'light' : 'dark');

export const STATUS_LABELS = Object.fromEntries(
  Object.entries(STATUS_VOCABULARY).map(([key, value]) => [key, value.label])
);

export const severityConfig = (score, mode = 'light') => {
  const numeric = Number(score || 0);
  const tier = SEVERITY_TIERS.find((item) => numeric >= item.min) || SEVERITY_TIERS[SEVERITY_TIERS.length - 1];
  return { ...tier, color: paletteFor(mode).severity[tier.key] };
};

export const statusMeta = (status, mode = 'light') => {
  const key = String(status || '').toLowerCase();
  const vocab = STATUS_VOCABULARY[key];
  const palette = paletteFor(mode);
  const toneKey = vocab?.tone || 'muted';
  return {
    key,
    label: vocab?.label || String(status || 'Unknown'),
    color: palette.tone[toneKey] || palette.textTertiary,
    glyph: vocab?.glyph || 'dot'
  };
};

export const envAccent = (slug, mode = 'light') => {
  const palette = paletteFor(mode);
  return isEmphasisedEnv(slug) ? palette.accent : palette.textTertiary;
};

export const roleColor = (role, mode = 'light') => {
  const palette = paletteFor(mode);
  const key = String(role || '').toLowerCase();
  if (key === 'admin') return palette.severity.critical;
  if (key === 'manager') return palette.accent;
  if (key === 'pentester') return palette.severity.high;
  return palette.textTertiary;
};

export const RECORD_STATUS_LABELS = {
  unchanged: 'Active',
  updated: 'Updated',
  missing: 'Missing'
};

export const recordStatusMeta = (status, mode = 'light') => {
  const key = String(status || '').toLowerCase();
  if (!RECORD_STATUS_LABELS[key]) return null;
  const palette = paletteFor(mode);
  const color =
    key === 'unchanged'
      ? palette.lifecycle.positive
      : key === 'missing'
        ? palette.severity.high
        : palette.accent;
  return { key, label: RECORD_STATUS_LABELS[key], color };
};

export const notificationColor = (type, mode = 'light') => {
  const palette = paletteFor(mode);
  const key = String(type || '').toLowerCase();
  if (key.includes('fail') || key.includes('conflict') || key === 'finding_added') {
    return palette.severity.critical;
  }
  if (key.includes('success') || key === 'collaborator_added') {
    return palette.lifecycle.positive;
  }
  if (key === 'collaborator_removed') return palette.severity.high;
  return palette.textTertiary;
};

const DASHBOARD_KEYS = {
  assets: 'accent',
  coverage: 'accent',
  risk: 'critical',
  throughput: 'deferred',
  started: 'accent',
  completed: 'positive',
  detected: 'high',
  resolved: 'deferred'
};

export const dashboardAccent = (key, mode = 'light') => {
  const palette = paletteFor(mode);
  const tone = DASHBOARD_KEYS[String(key || '').toLowerCase()] || 'accent';
  return palette.tone[tone] || palette.accent;
};

export const dashboardAccents = (mode = 'light') => {
  const palette = paletteFor(mode);
  return Object.fromEntries(
    Object.entries(DASHBOARD_KEYS).map(([key, tone]) => [key, palette.tone[tone] || palette.accent])
  );
};

export const OCCURRENCE_STATUS_OPTIONS = ['open', 'retest', 'fixed', 'not_affected', 'accepted'];

export const OPEN_LIKE_STATUSES = ['open', 'draft', 'retest'];

export const EXPORT_PACKAGES = [
  {
    key: 'owner_delivery',
    label: 'Owner delivery',
    blurb: 'Production only, drafts off. What you hand to the application owner.'
  },
  {
    key: 'wave_archive',
    label: 'Wave archive',
    blurb: 'Everything in this engagement. Environments are the ones on the wave.'
  },
  {
    key: 'retest_pack',
    label: 'Retest pack',
    blurb: 'Only occurrences still open or queued for retest.'
  },
  {
    key: 'internal_draft',
    label: 'Internal draft',
    blurb: 'Internal review copy. Draft findings may be included.'
  }
];

export const packageMeta = (key) =>
  EXPORT_PACKAGES.find((item) => item.key === key) || EXPORT_PACKAGES[0];
