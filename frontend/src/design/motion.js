/**
 * The RAPTOR motion vocabulary.
 *
 * This is a closed set. Motion in this product confirms what changed and where
 * it went; it never entertains. Anything not expressible with the transitions
 * and variants below does not belong in the interface.
 *
 * Two rules do most of the work:
 *
 *   1. `bounce: 0` everywhere. Serious tools do not overshoot — an operator
 *      reading a findings table should never watch a number wobble past its
 *      value and settle back.
 *   2. Nothing runs longer than 280ms except a path draw, which is allowed
 *      500ms because it is conveying the shape of data rather than a state
 *      change.
 *   3. The page does not leave the screen for a loading state. Chrome stays;
 *      data updates in place. Route fades are opacity-only and only run when
 *      `routeShellKey` changes — see `navigation.js`.
 *
 * Durations are exported in both milliseconds (for CSS and MUI, which want
 * `150ms`) and seconds (for Motion, which wants `0.15`).
 */

/** Milliseconds. Use for CSS transitions and MUI theme values. */
export const DURATION = {
  instant: 90,
  fast: 140,
  base: 200,
  slow: 280,
  draw: 500
};

/** Seconds. Use for Motion's `transition` prop. */
export const SECONDS = {
  instant: DURATION.instant / 1000,
  fast: DURATION.fast / 1000,
  base: DURATION.base / 1000,
  slow: DURATION.slow / 1000,
  draw: DURATION.draw / 1000
};

/**
 * Motion easing names are camelCase. Things arrive decisively (`easeOut`),
 * leave without ceremony (`easeIn`), and travel distance on `circOut`.
 */
export const EASE = {
  enter: 'easeOut',
  exit: 'easeIn',
  travel: 'circOut',
  inOut: 'easeInOut'
};

/** CSS equivalents, for the handful of places MUI drives the transition. */
export const CSS_EASE = {
  enter: 'cubic-bezier(0, 0, 0.58, 1)',
  exit: 'cubic-bezier(0.42, 0, 1, 1)',
  travel: 'cubic-bezier(0, 0.55, 0.45, 1)'
};

/* -------------------------------------------------------------------------- */
/* Named transitions                                                          */
/* -------------------------------------------------------------------------- */

export const TRANSITION = {
  /** Content arriving: route bodies, panels, rows. */
  enter: { duration: SECONDS.base, ease: EASE.enter },
  /** Content leaving. Always quicker than its entrance. */
  exit: { duration: SECONDS.fast, ease: EASE.exit },
  /** Immediate acknowledgement: hover tints, press states. */
  press: { duration: SECONDS.instant, ease: EASE.enter },
  /**
   * Something travelling across the screen under its own momentum — the tab
   * indicator, a reordering row. Interruptible, so it is a spring.
   */
  move: { type: 'spring', bounce: 0, visualDuration: SECONDS.base },
  /** Layout reflow driven by `layout` / `layoutId`. */
  layout: { type: 'spring', bounce: 0, visualDuration: 0.22 },
  /** A value counting to its new figure. */
  value: { type: 'spring', bounce: 0, visualDuration: 0.4 },
  /** Path drawing for sparklines and bars. Runs once, on first paint. */
  draw: { duration: SECONDS.draw, ease: EASE.enter }
};

/** The app-wide fallback handed to `MotionConfig`. */
export const DEFAULT_TRANSITION = TRANSITION.enter;

/* -------------------------------------------------------------------------- */
/* Variants                                                                   */
/* -------------------------------------------------------------------------- */

/** Route body. Cuts — a fade plus a cold-start loader is a blank screen. */
export const routeVariants = {
  initial: { opacity: 1 },
  animate: { opacity: 1 },
  exit: { opacity: 1 }
};

/** Dialogs and popovers. */
export const panelVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: TRANSITION.enter },
  exit: { opacity: 0, y: 4, transition: TRANSITION.exit }
};

export const scrimVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: { duration: SECONDS.fast } },
  exit: { opacity: 0, transition: { duration: SECONDS.fast } }
};

/** Right-hand drawer. */
export const drawerVariants = {
  initial: { opacity: 0, x: 16 },
  animate: { opacity: 1, x: 0, transition: TRANSITION.enter },
  exit: { opacity: 0, x: 16, transition: TRANSITION.exit }
};

/** A row entering or leaving a `DataList`. */
export const rowVariants = {
  initial: { opacity: 0 },
  animate: { opacity: 1, transition: TRANSITION.enter },
  exit: { opacity: 0, transition: TRANSITION.exit }
};

/** Expand-in-place disclosure. */
export const disclosureVariants = {
  initial: { height: 0, opacity: 0 },
  animate: { height: 'auto', opacity: 1, transition: TRANSITION.enter },
  exit: { height: 0, opacity: 0, transition: TRANSITION.exit }
};

/** Toasts. */
export const toastVariants = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0, transition: TRANSITION.enter },
  exit: { opacity: 0, y: 8, transition: TRANSITION.exit }
};

/** A live event arriving in the scan feed — the one continuously moving surface. */
export const feedVariants = {
  initial: { opacity: 0, x: -8 },
  animate: { opacity: 1, x: 0, transition: { duration: SECONDS.fast, ease: EASE.enter } },
  exit: { opacity: 0, transition: TRANSITION.exit }
};

/* -------------------------------------------------------------------------- */
/* Gestures                                                                   */
/* -------------------------------------------------------------------------- */

/**
 * Press feedback belongs to buttons only. Rows never scale — a table that
 * flexes under the cursor reads as a toy.
 */
export const pressable = {
  whileTap: { scale: 0.98 },
  transition: TRANSITION.press
};

/* -------------------------------------------------------------------------- */
/* Reduced motion                                                             */
/* -------------------------------------------------------------------------- */

/**
 * `MotionConfig reducedMotion="user"` already drops transform and layout
 * animations while keeping opacity. This helper covers the cases Motion cannot
 * infer — a distance we compute ourselves, or an effect we want to skip
 * outright.
 */
export const reduce = (prefersReduced, value, fallback = 0) =>
  prefersReduced ? fallback : value;

/** Shared `layoutId` keys, kept together so they cannot collide. */
export const LAYOUT_ID = {
  navIndicator: 'raptor-nav-indicator',
  tabIndicator: 'raptor-tab-indicator',
  envCoverageRail: 'raptor-env-coverage-rail'
};
