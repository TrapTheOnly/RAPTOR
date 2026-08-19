/**
 * RAPTOR "Operator Console" design tokens.
 *
 * Dark is the canonical mode; light is a faithful inversion rather than an
 * afterthought. Neutrals carry a slight cool cast so they read as screen
 * rather than paper.
 *
 * Colour is rationed. There is exactly one interactive accent, chosen outside
 * the red/orange/amber band so it can never be mistaken for severity. Severity
 * is a monotonic warm temperature ramp, which keeps it ordered even in
 * greyscale. Everything else is neutral: if something on screen is coloured,
 * it means something.
 *
 * Every foreground value here clears 4.5:1 against the worst-case surface of
 * its own mode (`raised` in dark, `surface` in light).
 */

/* -------------------------------------------------------------------------- */
/* Type                                                                       */
/* -------------------------------------------------------------------------- */

export const FONTS = {
  sans: "'Geist Variable', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  mono: "'Geist Mono Variable', ui-monospace, SFMono-Regular, Menlo, monospace"
};

/**
 * A tight, functional scale. Body sits at 13px rather than the usual 14-16 —
 * this is a density decision, and the whole layout model depends on it.
 *
 * `eyebrow` and `micro` are mono because they label machine data.
 */
export const TYPE = {
  display: { fontSize: 28, lineHeight: '32px', fontWeight: 600, letterSpacing: '-0.02em' },
  h1: { fontSize: 20, lineHeight: '28px', fontWeight: 600, letterSpacing: '-0.015em' },
  h2: { fontSize: 16, lineHeight: '24px', fontWeight: 600, letterSpacing: '-0.01em' },
  eyebrow: {
    fontSize: 13,
    lineHeight: '20px',
    fontWeight: 600,
    letterSpacing: '0.06em',
    textTransform: 'uppercase',
    fontFamily: FONTS.mono
  },
  body: { fontSize: 13, lineHeight: '20px', fontWeight: 400 },
  bodyStrong: { fontSize: 13, lineHeight: '20px', fontWeight: 500 },
  meta: { fontSize: 12, lineHeight: '16px', fontWeight: 400 },
  micro: {
    fontSize: 11,
    lineHeight: '16px',
    fontWeight: 500,
    letterSpacing: '0.04em',
    textTransform: 'uppercase',
    fontFamily: FONTS.mono
  },
  metric: {
    fontSize: 24,
    lineHeight: '28px',
    fontWeight: 500,
    letterSpacing: '-0.02em',
    fontFamily: FONTS.mono,
    fontVariantNumeric: 'tabular-nums'
  }
};

/* -------------------------------------------------------------------------- */
/* Space, shape, structure                                                    */
/* -------------------------------------------------------------------------- */

/** 4px grid. Named by pixel value so call sites read literally. */
export const SPACE = {
  x2: 2,
  x4: 4,
  x6: 6,
  x8: 8,
  x12: 12,
  x16: 16,
  x20: 20,
  x24: 24,
  x32: 32,
  x40: 40,
  x56: 56,
  x72: 72
};

/** Sharp by default. Nothing in this system is a pill. */
export const RADIUS = {
  none: 0,
  chip: 2,
  base: 4,
  panel: 6,
  round: 999
};

export const ROW = {
  compact: 32,
  base: 36,
  comfortable: 44
};

export const LAYOUT = {
  navHeight: 48,
  maxContent: 1600,
  gutter: 24,
  railWidth: 2
};

export const Z = {
  base: 0,
  sticky: 10,
  nav: 100,
  drawer: 1200,
  dialog: 1300,
  palette: 1400,
  toast: 1500,
  tooltip: 1600
};

/* -------------------------------------------------------------------------- */
/* Colour                                                                     */
/* -------------------------------------------------------------------------- */

/** Composite a hex colour onto a token at a given alpha. */
export const alpha = (hex, amount) => {
  const clean = String(hex).replace('#', '');
  const [r, g, b] = [0, 2, 4].map((offset) => parseInt(clean.slice(offset, offset + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${amount})`;
};

const SUBSTRATE = {
  dark: {
    canvas: '#08090B',
    surface: '#0E1013',
    raised: '#14171B',
    hover: '#171A1F',
    line: '#1E2228',
    lineStrong: '#2A2F37',
    text: '#E6E8EB',
    textSecondary: '#9BA1AA',
    textTertiary: '#7A818C',
    scrim: 'rgba(0, 0, 0, 0.72)'
  },
  light: {
    canvas: '#FBFBFC',
    surface: '#FFFFFF',
    raised: '#FFFFFF',
    hover: '#F4F5F7',
    line: '#E8EAED',
    lineStrong: '#D6DAE0',
    text: '#0C0E12',
    textSecondary: '#565D68',
    textTertiary: '#6A727E',
    scrim: 'rgba(12, 14, 18, 0.56)'
  }
};

/**
 * The single interactive accent. Electric cyan in dark, deepened to teal in
 * light so it still clears 4.5:1 on white.
 *
 * Swapping RAPTOR to a phosphor-lime identity is a change to these two values
 * and nothing else.
 */
const ACCENT = {
  dark: '#35D6E8',
  light: '#067A8A'
};

/**
 * Severity as temperature. Monotonic from hot to cold, so the ordering
 * survives greyscale and colour-blindness — and never collides with the accent.
 */
const SEVERITY = {
  dark: {
    critical: '#FF4747',
    high: '#FF8A00',
    medium: '#E3B341',
    low: '#8B949E',
    none: '#7A818C'
  },
  light: {
    critical: '#C6262E',
    high: '#9A4A08',
    medium: '#7A5B12',
    low: '#5A6472',
    none: '#6A727E'
  }
};

/** Lifecycle hues. Status leads with a glyph; colour is only reinforcement. */
const LIFECYCLE = {
  dark: { positive: '#3FB950', deferred: '#A78BFA' },
  light: { positive: '#1A7F37', deferred: '#5B4BC4' }
};

export const SEVERITY_TIERS = [
  { key: 'critical', label: 'Critical', min: 9 },
  { key: 'high', label: 'High', min: 7 },
  { key: 'medium', label: 'Medium', min: 4 },
  { key: 'low', label: 'Low', min: 0.1 },
  { key: 'none', label: 'Unscored', min: -1 }
];

/**
 * Status glyphs. The shape carries the meaning so severity and status are
 * never distinguishable by colour alone.
 *
 * `dot` filled · `ring` hollow · `half` half-filled · `check` resolved
 * · `slash` ruled out
 */
export const STATUS_VOCABULARY = {
  open: { label: 'Open', glyph: 'dot', tone: 'critical' },
  draft: { label: 'Draft', glyph: 'ring', tone: 'muted' },
  retest: { label: 'Retest', glyph: 'half', tone: 'medium' },
  fixed: { label: 'Fixed', glyph: 'check', tone: 'positive' },
  accepted: { label: 'Accepted', glyph: 'ring', tone: 'deferred' },
  not_affected: { label: 'Not affected', glyph: 'slash', tone: 'muted' }
};

/**
 * Chart series. Deliberately short: four distinguishable steps and a neutral.
 * Dashboards that need more than this need fewer series, not more colours.
 */
const seriesFor = (mode) => [
  ACCENT[mode],
  LIFECYCLE[mode].deferred,
  SEVERITY[mode].high,
  LIFECYCLE[mode].positive,
  SUBSTRATE[mode].textSecondary
];

/**
 * Resolve the full palette for a mode. This is the single source every other
 * part of the design system reads from.
 */
export const getPalette = (mode = 'dark') => {
  const key = mode === 'light' ? 'light' : 'dark';
  const base = SUBSTRATE[key];
  const accent = ACCENT[key];
  const severity = SEVERITY[key];
  const lifecycle = LIFECYCLE[key];

  return {
    mode: key,
    ...base,
    accent,
    accentFill: alpha(accent, key === 'dark' ? 0.14 : 0.1),
    accentLine: alpha(accent, key === 'dark' ? 0.36 : 0.28),
    severity,
    lifecycle,
    /** Tone lookup used by status glyphs and inline emphasis. */
    tone: {
      critical: severity.critical,
      high: severity.high,
      medium: severity.medium,
      low: severity.low,
      positive: lifecycle.positive,
      deferred: lifecycle.deferred,
      accent,
      muted: base.textTertiary,
      neutral: base.textSecondary
    },
    series: seriesFor(key),
    /** Depth in dark mode is a surface step plus a hairline, never a shadow. */
    shadow:
      key === 'dark'
        ? 'none'
        : '0 1px 2px rgba(12, 14, 18, 0.06), 0 8px 24px rgba(12, 14, 18, 0.08)'
  };
};

/* -------------------------------------------------------------------------- */
/* Environment labels                                                         */
/* -------------------------------------------------------------------------- */

/**
 * Environments are not a rainbow. Every environment renders as a neutral mono
 * micro-label; only production is emphasised, because production is the only
 * one where being wrong is expensive.
 */
export const EMPHASISED_ENVS = ['prod', 'production'];

export const isEmphasisedEnv = (slug) =>
  EMPHASISED_ENVS.includes(String(slug || '').trim().toLowerCase());
