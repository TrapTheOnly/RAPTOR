/**
 * The MUI theme for the Operator Console language.
 *
 * MUI stays as the engine — it carries focus management, portals, and form
 * behaviour across the app — but none of its appearance survives. Every
 * component in active use is overridden here, which means screens that have
 * not yet been rewritten onto the primitives still inherit the new substrate,
 * type, and shape rather than sitting in the old look.
 */

import { createTheme } from '@mui/material/styles';
import Fade from '@mui/material/Fade';
import { FONTS, TYPE, RADIUS, ROW, Z, getPalette, alpha } from './tokens';
import { DURATION, CSS_EASE } from './motion';

/** Inputs, buttons and rows all share one control height so lines align. */
const CONTROL_HEIGHT = 32;

export const createRaptorTheme = (darkMode) => {
  const mode = darkMode ? 'dark' : 'light';
  const p = getPalette(mode);
  const isDark = mode === 'dark';

  const focusRing = {
    outline: `2px solid ${p.accent}`,
    outlineOffset: 2
  };

  const menuSurface = {
    backgroundColor: p.raised,
    backgroundImage: 'none',
    border: `1px solid ${p.lineStrong}`,
    borderRadius: RADIUS.panel,
    overflow: 'hidden',
    boxShadow: isDark
      ? `0 0 0 1px ${p.lineStrong}`
      : '0 12px 32px rgba(12, 14, 18, 0.16), 0 0 0 1px rgba(12, 14, 18, 0.08)'
  };

  return createTheme({
    raptor: p,
    palette: {
      mode,
      primary: { main: p.accent, contrastText: isDark ? p.canvas : '#FFFFFF' },
      secondary: { main: p.lifecycle.deferred },
      error: { main: p.severity.critical },
      warning: { main: p.severity.high },
      info: { main: p.accent },
      success: { main: p.lifecycle.positive },
      background: { default: p.canvas, paper: p.surface },
      text: {
        primary: p.text,
        secondary: p.textSecondary,
        disabled: p.textTertiary
      },
      divider: p.line,
      action: {
        hover: p.hover,
        selected: p.accentFill,
        disabled: p.textTertiary,
        disabledBackground: p.line,
        focus: p.accentFill
      }
    },

    shape: { borderRadius: RADIUS.base },

    zIndex: {
      appBar: Z.nav,
      drawer: Z.drawer,
      modal: Z.dialog,
      snackbar: Z.toast,
      tooltip: Z.tooltip
    },

    transitions: {
      duration: {
        shortest: DURATION.instant,
        shorter: DURATION.fast,
        short: DURATION.fast,
        standard: DURATION.base,
        complex: DURATION.slow,
        enteringScreen: DURATION.base,
        leavingScreen: DURATION.fast
      },
      easing: {
        easeInOut: CSS_EASE.travel,
        easeOut: CSS_EASE.enter,
        easeIn: CSS_EASE.exit,
        sharp: CSS_EASE.travel
      }
    },

    typography: {
      fontFamily: FONTS.sans,
      fontSize: 13,
      htmlFontSize: 16,
      h1: TYPE.display,
      h2: TYPE.h1,
      h3: TYPE.h1,
      h4: TYPE.h1,
      h5: TYPE.h2,
      h6: TYPE.h2,
      subtitle1: TYPE.bodyStrong,
      subtitle2: { ...TYPE.meta, fontWeight: 500 },
      body1: TYPE.body,
      body2: TYPE.meta,
      button: { ...TYPE.bodyStrong, textTransform: 'none', letterSpacing: 0 },
      caption: TYPE.meta,
      overline: TYPE.micro
    },

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          ':root': {
            colorScheme: mode,
            '--raptor-canvas': p.canvas,
            '--raptor-surface': p.surface,
            '--raptor-raised': p.raised,
            '--raptor-hover': p.hover,
            '--raptor-line': p.line,
            '--raptor-line-strong': p.lineStrong,
            '--raptor-text': p.text,
            '--raptor-text-secondary': p.textSecondary,
            '--raptor-text-tertiary': p.textTertiary,
            '--raptor-accent': p.accent,
            '--raptor-accent-fill': p.accentFill,
            '--raptor-font-sans': FONTS.sans,
            '--raptor-font-mono': FONTS.mono
          },
          body: {
            backgroundColor: p.canvas,
            color: p.text,
            fontFamily: FONTS.sans,
            fontSize: 13,
            lineHeight: '20px',
            WebkitFontSmoothing: 'antialiased',
            MozOsxFontSmoothing: 'grayscale',
            textRendering: 'optimizeLegibility'
          },
          // Machine-generated text is monospaced with aligned figures, so a
          // column of hosts or scores can be scanned rather than read.
          'code, pre, kbd, samp': {
            fontFamily: FONTS.mono,
            fontVariantNumeric: 'tabular-nums'
          },
          '::selection': {
            backgroundColor: alpha(p.accent, 0.28),
            color: p.text
          },
          '*:focus-visible': focusRing,
          '::-webkit-scrollbar': { width: 10, height: 10 },
          '::-webkit-scrollbar-track': { background: 'transparent' },
          '::-webkit-scrollbar-thumb': {
            background: p.lineStrong,
            borderRadius: RADIUS.round,
            border: `2px solid ${p.canvas}`
          },
          '::-webkit-scrollbar-thumb:hover': { background: p.textTertiary }
        }
      },

      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: p.surface,
            color: p.text
          },
          outlined: { border: `1px solid ${p.line}` },
          // Depth in dark mode is a surface step plus a hairline, never a shadow.
          elevation1: {
            backgroundColor: p.raised,
            border: `1px solid ${p.line}`,
            boxShadow: p.shadow
          },
          elevation8: {
            backgroundColor: p.raised,
            border: `1px solid ${p.line}`,
            boxShadow: p.shadow
          }
        }
      },

      MuiCard: {
        defaultProps: { elevation: 0, variant: 'outlined' },
        styleOverrides: {
          root: {
            backgroundImage: 'none',
            backgroundColor: p.surface,
            border: `1px solid ${p.line}`,
            borderRadius: RADIUS.base
          }
        }
      },
      MuiCardContent: {
        styleOverrides: {
          root: { padding: 16, '&:last-child': { paddingBottom: 16 } }
        }
      },
      MuiCardHeader: {
        styleOverrides: {
          root: { padding: 16, borderBottom: `1px solid ${p.line}` },
          title: TYPE.h2,
          subheader: { ...TYPE.meta, color: p.textSecondary }
        }
      },

      MuiButton: {
        defaultProps: { disableElevation: true, disableRipple: true },
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: RADIUS.base,
            fontWeight: 500,
            fontSize: 13,
            lineHeight: '20px',
            minHeight: CONTROL_HEIGHT,
            padding: '5px 12px',
            transition: `background-color ${DURATION.instant}ms ${CSS_EASE.enter}, border-color ${DURATION.instant}ms ${CSS_EASE.enter}, color ${DURATION.instant}ms ${CSS_EASE.enter}`,
            '&:focus-visible': focusRing
          },
          sizeSmall: { minHeight: CONTROL_HEIGHT, padding: '5px 10px', fontSize: 13 },
          sizeLarge: { minHeight: 36, padding: '7px 16px' },
          contained: {
            backgroundColor: p.accent,
            color: isDark ? p.canvas : '#FFFFFF',
            fontWeight: 600,
            '&:hover': { backgroundColor: p.accent, filter: 'brightness(1.08)' },
            '&.Mui-disabled': {
              backgroundColor: p.lineStrong,
              color: p.textSecondary,
              opacity: 1
            }
          },
          outlined: {
            borderColor: p.lineStrong,
            color: p.text,
            '&:hover': { borderColor: p.textTertiary, backgroundColor: p.hover }
          },
          text: {
            color: p.textSecondary,
            '&:hover': { backgroundColor: p.hover, color: p.text }
          }
        }
      },

      MuiIconButton: {
        defaultProps: { disableRipple: true },
        styleOverrides: {
          root: {
            borderRadius: RADIUS.base,
            color: p.textSecondary,
            transition: `background-color ${DURATION.instant}ms ${CSS_EASE.enter}, color ${DURATION.instant}ms ${CSS_EASE.enter}`,
            '&:hover': { backgroundColor: p.hover, color: p.text },
            '&:focus-visible': focusRing
          },
          sizeSmall: { padding: 5 }
        }
      },

      MuiToggleButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
            borderRadius: RADIUS.base,
            borderColor: p.line,
            color: p.textSecondary,
            minHeight: CONTROL_HEIGHT,
            fontSize: 12,
            '&.Mui-selected': {
              backgroundColor: p.accentFill,
              color: p.accent,
              borderColor: p.accentLine
            }
          }
        }
      },

      MuiInputBase: {
        styleOverrides: {
          root: {
            fontSize: 13,
            lineHeight: '20px',
            color: p.text,
            backgroundColor: isDark ? p.canvas : p.surface
          },
          input: {
            '&::placeholder': { color: p.textTertiary, opacity: 1 }
          }
        }
      },

      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            borderRadius: RADIUS.base,
            backgroundColor: isDark ? p.canvas : p.surface,
            transition: `border-color ${DURATION.instant}ms ${CSS_EASE.enter}`,
            '& .MuiOutlinedInput-notchedOutline': { borderColor: p.lineStrong },
            '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: p.textTertiary },
            '&:hover .MuiSelect-icon, &:hover .MuiAutocomplete-endAdornment .MuiSvgIcon-root': {
              color: p.text
            },
            '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
              borderColor: p.accent,
              borderWidth: 1
            },
            '&.Mui-focused .MuiSelect-icon, &.Mui-focused .MuiAutocomplete-popupIndicator': {
              color: p.accent
            },
            '&.Mui-focused': { boxShadow: `0 0 0 2px ${alpha(p.accent, 0.24)}` },
            '&.Mui-error .MuiOutlinedInput-notchedOutline': { borderColor: p.severity.critical }
          },
          input: { padding: '6px 10px', height: 20, boxSizing: 'content-box' },
          inputSizeSmall: { padding: '6px 10px', height: 20 },
          multiline: { padding: 0 }
        }
      },

      MuiFilledInput: {
        styleOverrides: {
          root: { backgroundColor: p.raised, borderRadius: RADIUS.base }
        }
      },

      MuiInputLabel: {
        styleOverrides: {
          root: {
            fontSize: 13,
            color: p.textSecondary,
            '&.Mui-focused': { color: p.accent }
          }
        }
      },

      MuiFormHelperText: {
        styleOverrides: {
          root: { ...TYPE.meta, marginLeft: 2, color: p.textTertiary }
        }
      },

      MuiFormControlLabel: {
        styleOverrides: {
          label: { fontSize: 13, lineHeight: '20px' }
        }
      },

      MuiSelect: {
        styleOverrides: {
          select: { padding: '6px 10px', minHeight: 20 },
          icon: {
            color: p.textTertiary,
            transition: `color ${DURATION.instant}ms ${CSS_EASE.enter}`
          },
          iconOpen: { color: p.accent }
        }
      },

      MuiMenu: {
        defaultProps: {
          hideBackdrop: false,
          disableScrollLock: true,
          slotProps: { backdrop: { invisible: true } },
          TransitionComponent: Fade,
          TransitionProps: { timeout: { enter: DURATION.fast, exit: DURATION.instant } }
        },
        styleOverrides: {
          paper: menuSurface,
          list: { padding: 4 }
        }
      },

      MuiMenuItem: {
        defaultProps: { disableRipple: true },
        styleOverrides: {
          root: {
            fontSize: 13,
            minHeight: CONTROL_HEIGHT,
            borderRadius: RADIUS.chip,
            padding: '6px 8px',
            '&:hover': { backgroundColor: p.hover },
            '&.Mui-selected': {
              backgroundColor: p.accentFill,
              color: p.accent,
              '&:hover': { backgroundColor: p.accentFill }
            }
          }
        }
      },

      MuiPopover: {
        defaultProps: {
          TransitionComponent: Fade,
          TransitionProps: { timeout: { enter: DURATION.fast, exit: DURATION.instant } }
        },
        styleOverrides: {
          paper: menuSurface
        }
      },

      MuiAutocomplete: {
        styleOverrides: {
          paper: menuSurface,
          listbox: { padding: 4 },
          option: {
            fontSize: 13,
            minHeight: CONTROL_HEIGHT,
            borderRadius: RADIUS.chip,
            '&[aria-selected="true"]': { backgroundColor: p.accentFill, color: p.accent }
          },
          inputRoot: {
            paddingTop: '0 !important',
            paddingBottom: '0 !important',
            minHeight: CONTROL_HEIGHT,
            '& .MuiOutlinedInput-input': { padding: '6px 10px' }
          },
          tag: {
            height: 20,
            margin: 2,
            textTransform: 'none',
            fontFamily: FONTS.sans,
            fontSize: 12,
            letterSpacing: 0,
            fontWeight: 500
          }
        }
      },

      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: RADIUS.chip,
            height: 20,
            fontFamily: FONTS.mono,
            fontSize: 11,
            fontWeight: 500,
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            backgroundColor: isDark ? p.raised : p.hover,
            color: p.textSecondary,
            border: `1px solid ${p.line}`
          },
          label: { paddingLeft: 6, paddingRight: 6 },
          sizeSmall: { height: 18, fontSize: 10 },
          outlined: { backgroundColor: 'transparent' },
          deleteIcon: { fontSize: 13, color: p.textTertiary, marginRight: 3 }
        }
      },

      MuiTabs: {
        styleOverrides: {
          root: { minHeight: 40, borderBottom: `1px solid ${p.line}` },
          indicator: { height: 1, backgroundColor: p.accent }
        }
      },

      MuiTab: {
        defaultProps: { disableRipple: true },
        styleOverrides: {
          root: {
            textTransform: 'none',
            fontWeight: 500,
            fontSize: 13,
            minHeight: 40,
            minWidth: 0,
            padding: '0 12px',
            color: p.textSecondary,
            '&:hover': { color: p.text },
            '&.Mui-selected': { color: p.text },
            '&:focus-visible': focusRing
          }
        }
      },

      MuiTable: {
        styleOverrides: {
          root: { borderCollapse: 'separate', borderSpacing: 0 }
        }
      },
      MuiTableCell: {
        styleOverrides: {
          root: {
            fontSize: 13,
            lineHeight: '20px',
            padding: '8px 12px',
            borderBottom: `1px solid ${p.line}`
          },
          head: {
            ...TYPE.micro,
            color: p.textTertiary,
            backgroundColor: p.canvas,
            borderBottom: `1px solid ${p.line}`
          }
        }
      },
      MuiTableRow: {
        styleOverrides: {
          root: {
            '&:hover': { backgroundColor: p.hover },
            '&:last-child td': { borderBottom: 'none' }
          }
        }
      },

      MuiDialog: {
        defaultProps: { hideBackdrop: false },
        styleOverrides: {
          paper: {
            backgroundColor: p.raised,
            backgroundImage: 'none',
            border: `1px solid ${isDark ? p.line : p.lineStrong}`,
            borderRadius: RADIUS.panel,
            boxShadow: isDark
              ? p.shadow
              : '0 24px 64px rgba(12, 14, 18, 0.28), 0 0 0 1px rgba(12, 14, 18, 0.08)'
          }
        }
      },
      MuiModal: {
        styleOverrides: {
          backdrop: {
            backgroundColor: p.scrim
          }
        }
      },
      MuiBackdrop: {
        styleOverrides: {
          root: {
            backgroundColor: p.scrim
          },
          invisible: { backgroundColor: 'transparent' }
        }
      },
      MuiDialogTitle: {
        styleOverrides: {
          root: { ...TYPE.h2, padding: '14px 16px', borderBottom: `1px solid ${p.line}` }
        }
      },
      MuiDialogContent: {
        styleOverrides: {
          root: { padding: 16 }
        }
      },
      MuiDialogActions: {
        styleOverrides: {
          root: { padding: 12, gap: 8, borderTop: `1px solid ${p.line}` }
        }
      },
      MuiDialogContentText: {
        styleOverrides: {
          root: { fontSize: 13, lineHeight: '20px', color: p.textSecondary }
        }
      },

      MuiDrawer: {
        styleOverrides: {
          paper: {
            backgroundColor: p.surface,
            backgroundImage: 'none',
            borderColor: p.line
          }
        }
      },

      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: isDark ? p.raised : '#101418',
            color: isDark ? p.text : '#FFFFFF',
            border: isDark ? `1px solid ${p.line}` : 'none',
            borderRadius: RADIUS.base,
            fontSize: 12,
            lineHeight: '16px',
            padding: '5px 8px',
            fontWeight: 400
          },
          arrow: { color: isDark ? p.raised : '#101418' }
        }
      },

      MuiAlert: {
        styleOverrides: {
          // Alerts are a bordered surface, not a colour wash. The severity
          // reads from the border and the icon, so a warning does not repaint
          // a third of the screen.
          root: {
            borderRadius: RADIUS.base,
            fontSize: 13,
            padding: '6px 12px',
            border: `1px solid ${p.line}`,
            backgroundColor: p.surface,
            color: p.text
          },
          icon: { padding: '6px 0', marginRight: 10 },
          standardError: { borderColor: alpha(p.severity.critical, 0.4) },
          standardWarning: { borderColor: alpha(p.severity.high, 0.4) },
          standardSuccess: { borderColor: alpha(p.lifecycle.positive, 0.4) },
          standardInfo: { borderColor: p.accentLine },
          outlinedError: { borderColor: alpha(p.severity.critical, 0.4) },
          outlinedWarning: { borderColor: alpha(p.severity.high, 0.4) },
          outlinedSuccess: { borderColor: alpha(p.lifecycle.positive, 0.4) },
          outlinedInfo: { borderColor: p.accentLine }
        }
      },

      MuiSnackbarContent: {
        styleOverrides: {
          root: {
            backgroundColor: p.raised,
            color: p.text,
            border: `1px solid ${p.line}`,
            borderRadius: RADIUS.base,
            fontSize: 13,
            boxShadow: p.shadow
          }
        }
      },

      MuiLinearProgress: {
        styleOverrides: {
          root: { height: 2, borderRadius: 0, backgroundColor: p.line },
          bar: { borderRadius: 0, backgroundColor: p.accent }
        }
      },
      MuiCircularProgress: {
        styleOverrides: {
          root: { color: p.accent }
        }
      },

      MuiDivider: {
        styleOverrides: {
          root: { borderColor: p.line }
        }
      },

      MuiCheckbox: {
        defaultProps: { disableRipple: true, size: 'small' },
        styleOverrides: {
          root: {
            color: p.lineStrong,
            padding: 6,
            '&.Mui-checked': { color: p.accent },
            '&:focus-visible': focusRing
          }
        }
      },
      MuiRadio: {
        defaultProps: { disableRipple: true, size: 'small' },
        styleOverrides: {
          root: {
            color: p.lineStrong,
            padding: 6,
            '&.Mui-checked': { color: p.accent }
          }
        }
      },
      MuiSwitch: {
        styleOverrides: {
          root: { width: 34, height: 20, padding: 0 },
          switchBase: {
            padding: 2,
            '&.Mui-checked': {
              transform: 'translateX(14px)',
              color: isDark ? p.canvas : '#FFFFFF',
              '& + .MuiSwitch-track': { backgroundColor: p.accent, opacity: 1 }
            }
          },
          thumb: { width: 16, height: 16, boxShadow: 'none' },
          track: { borderRadius: RADIUS.round, backgroundColor: p.lineStrong, opacity: 1 }
        }
      },

      MuiAccordion: {
        defaultProps: { disableGutters: true, elevation: 0, square: true },
        styleOverrides: {
          root: {
            backgroundColor: 'transparent',
            borderBottom: `1px solid ${p.line}`,
            '&::before': { display: 'none' }
          }
        }
      },
      MuiAccordionSummary: {
        styleOverrides: {
          root: { minHeight: ROW.comfortable, padding: '0 12px' },
          content: { margin: '10px 0' }
        }
      },
      MuiAccordionDetails: {
        styleOverrides: {
          root: { padding: '0 12px 12px' }
        }
      },

      MuiListItemButton: {
        defaultProps: { disableRipple: true },
        styleOverrides: {
          root: {
            borderRadius: RADIUS.base,
            minHeight: CONTROL_HEIGHT,
            fontSize: 13,
            '&:hover': { backgroundColor: p.hover },
            '&.Mui-selected': {
              backgroundColor: p.accentFill,
              color: p.accent,
              '&:hover': { backgroundColor: p.accentFill }
            }
          }
        }
      },
      MuiListItemIcon: {
        styleOverrides: {
          root: { minWidth: 28, color: p.textTertiary }
        }
      },
      MuiListItemText: {
        styleOverrides: {
          primary: { fontSize: 13, lineHeight: '20px' },
          secondary: { ...TYPE.meta, color: p.textTertiary }
        }
      },

      MuiAvatar: {
        styleOverrides: {
          root: {
            borderRadius: RADIUS.base,
            backgroundColor: p.raised,
            color: p.textSecondary,
            fontFamily: FONTS.mono,
            fontSize: 11,
            fontWeight: 500
          }
        }
      },

      MuiBadge: {
        styleOverrides: {
          badge: {
            fontFamily: FONTS.mono,
            fontSize: 10,
            fontWeight: 500,
            minWidth: 16,
            height: 16,
            borderRadius: RADIUS.chip
          }
        }
      },

      MuiLink: {
        defaultProps: { underline: 'none' },
        styleOverrides: {
          root: {
            color: p.accent,
            '&:hover': { textDecoration: 'underline' },
            '&:focus-visible': focusRing
          }
        }
      },

      MuiBreadcrumbs: {
        styleOverrides: {
          root: { fontSize: 12, color: p.textTertiary },
          separator: { marginLeft: 6, marginRight: 6, color: p.lineStrong }
        }
      },

      MuiSkeleton: {
        defaultProps: { animation: 'wave' },
        styleOverrides: {
          root: { backgroundColor: p.hover, borderRadius: RADIUS.chip }
        }
      },

      MuiPagination: {
        styleOverrides: {
          root: { fontFamily: FONTS.mono }
        }
      },
      MuiPaginationItem: {
        styleOverrides: {
          root: {
            fontFamily: FONTS.mono,
            fontSize: 12,
            borderRadius: RADIUS.base,
            '&.Mui-selected': { backgroundColor: p.accentFill, color: p.accent }
          }
        }
      }
    }
  });
};

export default createRaptorTheme;
