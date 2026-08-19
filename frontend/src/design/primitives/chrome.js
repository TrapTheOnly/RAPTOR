import React from 'react';
import { motion } from 'motion/react';
import {
  Button as MuiButton,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  LinearProgress
} from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { FONTS, LAYOUT, RADIUS, SPACE, TYPE } from '../tokens';
import { CSS_EASE, DURATION, TRANSITION, panelVariants, pressable, scrimVariants } from '../motion';
import { LOADING_DEFER_MS } from '../navigation';
import { usePalette } from '../usePalette';
import { Text, Mono } from './type';

export const Surface = ({
  as: Tag = 'div',
  raised = false,
  selected = false,
  interactive = false,
  style,
  children,
  onMouseEnter,
  onMouseLeave,
  ...rest
}) => {
  const palette = usePalette();
  const [hovered, setHovered] = React.useState(false);
  const background = selected
    ? palette.accentFill
    : hovered && interactive
      ? palette.hover
      : raised
        ? palette.raised
        : palette.surface;

  return (
    <Tag
      aria-current={selected ? 'true' : undefined}
      onMouseEnter={(event) => {
        if (interactive) setHovered(true);
        onMouseEnter?.(event);
      }}
      onMouseLeave={(event) => {
        if (interactive) setHovered(false);
        onMouseLeave?.(event);
      }}
      style={{
        background,
        border: `1px solid ${selected ? palette.accentLine : palette.line}`,
        borderRadius: RADIUS.base,
        position: 'relative',
        transition: `background-color ${DURATION.instant}ms ${CSS_EASE.enter}, border-color ${DURATION.instant}ms ${CSS_EASE.enter}`,
        ...style
      }}
      {...rest}
    >
      {children}
    </Tag>
  );
};

export const Rule = ({ vertical = false, style }) => {
  const palette = usePalette();
  return (
    <div
      aria-hidden
      style={{
        background: palette.line,
        width: vertical ? 1 : '100%',
        height: vertical ? '100%' : 1,
        flexShrink: 0,
        ...style
      }}
    />
  );
};

const MotionButton = motion.create(MuiButton);

export const Button = ({ children, ...rest }) => (
  <MotionButton
    disableElevation
    disableRipple
    whileTap={pressable.whileTap}
    transition={TRANSITION.press}
    {...rest}
  >
    {children}
  </MotionButton>
);

/**
 * Label sits above the control, never in a field-set notch. Floating labels
 * are what made the old forms look smushed: the caption and the value fought
 * for the same 32px.
 */
export const Field = ({
  label,
  hint,
  error,
  helperText,
  fullWidth = true,
  style,
  ...props
}) => {
  const palette = usePalette();
  const { error: errorProp, helperText: helperTextProp, ...inputProps } = props;
  const message = error || helperText || helperTextProp || hint;
  return (
    <label
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        minWidth: 0,
        width: fullWidth ? '100%' : undefined,
        ...style
      }}
    >
      {label ? (
        <span style={{ ...TYPE.micro, color: palette.textTertiary }}>{label}</span>
      ) : null}
      <TextField
        size="small"
        fullWidth={fullWidth}
        {...inputProps}
        label={undefined}
        error={Boolean(error) || Boolean(errorProp)}
        helperText={message || undefined}
      />
    </label>
  );
};

export const SwitchRow = ({ label, hint, checked, onChange, disabled = false }) => {
  const palette = usePalette();
  return (
    <label
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        gap: SPACE.x16,
        padding: `${SPACE.x12}px 0`,
        cursor: disabled ? 'default' : 'pointer'
      }}
    >
      <span style={{ minWidth: 0 }}>
        <Text as="span" variant="bodyStrong" style={{ display: 'block' }}>
          {label}
        </Text>
        {hint ? (
          <Text as="span" variant="meta" tone="secondary" style={{ display: 'block', marginTop: 4 }}>
            {hint}
          </Text>
        ) : null}
      </span>
      <motion.span
        layout
        transition={TRANSITION.layout}
        style={{
          flexShrink: 0,
          width: 34,
          height: 20,
          borderRadius: 999,
          background: checked ? palette.accent : palette.lineStrong,
          position: 'relative',
          marginTop: 2,
          opacity: disabled ? 0.5 : 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: checked ? 'flex-end' : 'flex-start',
          padding: 2,
          boxSizing: 'border-box'
        }}
      >
        <motion.span
          layout
          transition={TRANSITION.layout}
          style={{
            width: 16,
            height: 16,
            borderRadius: 999,
            background: '#FFFFFF'
          }}
        />
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange?.(event.target.checked)}
          style={{ position: 'absolute', inset: 0, opacity: 0, cursor: disabled ? 'default' : 'pointer' }}
        />
      </motion.span>
    </label>
  );
};

export const Stepper = ({ value, onChange, min = 1, max = 10, disabled = false, label, hint, error }) => {
  const palette = usePalette();
  const numeric = Number(value);
  const atMin = numeric <= min;
  const atMax = numeric >= max;

  const bump = (delta) => {
    const next = numeric + delta;
    if (next < min || next > max) return;
    onChange(next);
  };

  return (
    <div>
      {label ? (
        <div style={{ ...TYPE.micro, color: palette.textTertiary, marginBottom: 6 }}>{label}</div>
      ) : null}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Button size="small" variant="outlined" disabled={disabled || atMin} onClick={() => bump(-1)}>
          −
        </Button>
        <Mono style={{ minWidth: 24, textAlign: 'center', fontSize: 16 }}>{Number.isFinite(numeric) ? numeric : '—'}</Mono>
        <Button size="small" variant="outlined" disabled={disabled || atMax} onClick={() => bump(1)}>
          +
        </Button>
      </div>
      {error || hint ? (
        <Text as="div" variant="meta" tone={error ? 'critical' : 'secondary'} style={{ marginTop: 6 }}>
          {error || hint}
        </Text>
      ) : null}
    </div>
  );
};

export const Tag = ({ children, emphasized = false, style, ...rest }) => {
  const palette = usePalette();
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        height: 18,
        padding: '0 6px',
        borderRadius: RADIUS.chip,
        border: `1px solid ${emphasized ? palette.accentLine : palette.line}`,
        color: emphasized ? palette.accent : palette.textSecondary,
        background: emphasized ? palette.accentFill : 'transparent',
        fontFamily: FONTS.mono,
        fontSize: 11,
        fontWeight: 500,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
        whiteSpace: 'nowrap',
        ...style
      }}
      {...rest}
    >
      {children}
    </span>
  );
};

export const EnvTag = ({ slug, label }) => (
  <Tag emphasized={String(slug || '').toLowerCase() === 'prod' || String(slug || '').toLowerCase() === 'production'}>
    {label || slug || 'unassigned'}
  </Tag>
);

const PanelPaper = React.forwardRef(function PanelPaper(
  { transitionDuration, ownerState, ...props },
  ref
) {
  return <motion.div ref={ref} {...props} />;
});

const PanelScrim = React.forwardRef(function PanelScrim(
  { transitionDuration, ownerState, style, open, appear, timeout, ...props },
  ref
) {
  const palette = usePalette();
  const { in: _in, ...rest } = props;
  return (
    <motion.div
      ref={ref}
      {...rest}
      aria-hidden
      style={{
        position: 'absolute',
        inset: 0,
        zIndex: -1,
        ...style,
        backgroundColor: palette.scrim
      }}
    />
  );
});

export const Panel = ({
  open,
  onClose,
  title,
  children,
  actions,
  maxWidth = 'sm',
  fullWidth = true
}) => (
  <Dialog
    open={open}
    onClose={onClose}
    maxWidth={maxWidth}
    fullWidth={fullWidth}
    hideBackdrop={false}
    slots={{ backdrop: PanelScrim }}
    slotProps={{
      backdrop: {
        variants: scrimVariants,
        initial: 'initial',
        animate: 'animate',
        exit: 'exit'
      }
    }}
    PaperComponent={PanelPaper}
    PaperProps={{
      variants: panelVariants,
      initial: 'initial',
      animate: 'animate',
      exit: 'exit'
    }}
  >
    {title ? <DialogTitle>{title}</DialogTitle> : null}
    <DialogContent style={{ display: 'flex', flexDirection: 'column', gap: 16, paddingTop: 16 }}>
      {children}
    </DialogContent>
    {actions ? <DialogActions>{actions}</DialogActions> : null}
  </Dialog>
);

export const EmptyState = ({ icon: Icon, title, hint, actions }) => {
  const palette = usePalette();
  return (
    <div
      style={{
        textAlign: 'center',
        padding: `${SPACE.x40}px ${SPACE.x24}px`,
        border: `1px dashed ${palette.lineStrong}`,
        borderRadius: RADIUS.base
      }}
    >
      {Icon ? (
        <Icon style={{ fontSize: 22, color: palette.textTertiary, marginBottom: SPACE.x12 }} />
      ) : null}
      <Text as="p" variant="h2">
        {title}
      </Text>
      {hint ? (
        <Text as="p" variant="meta" tone="secondary" style={{ marginTop: SPACE.x8, maxWidth: 480, marginLeft: 'auto', marginRight: 'auto' }}>
          {hint}
        </Text>
      ) : null}
      {actions ? <div style={{ marginTop: SPACE.x16 }}>{actions}</div> : null}
    </div>
  );
};

export const Skeleton = ({ width = '100%', height = 16, style }) => {
  const palette = usePalette();
  return (
    <div
      style={{
        width,
        height,
        borderRadius: RADIUS.chip,
        background: palette.hover,
        ...style
      }}
    />
  );
};

export const Toast = ({ open, message, severity = 'success', onClose, actionLabel, onAction }) => {
  const palette = usePalette();
  const tone =
    severity === 'error'
      ? palette.severity.critical
      : severity === 'warning'
        ? palette.severity.high
        : severity === 'info'
          ? palette.accent
          : palette.lifecycle.positive;

  if (!open) return null;

  return (
    <motion.div
      variants={panelVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      style={{
        position: 'fixed',
        right: SPACE.x24,
        bottom: SPACE.x24,
        zIndex: 1500,
        minWidth: 280,
        maxWidth: 420,
        padding: '10px 36px 10px 14px',
        background: palette.raised,
        border: `1px solid ${palette.line}`,
        borderLeft: `2px solid ${tone}`,
        borderRadius: RADIUS.base,
        boxShadow: palette.shadow,
        color: palette.text,
        fontSize: 13,
        lineHeight: '20px'
      }}
      role="status"
    >
      <button
        type="button"
        onClick={onClose}
        style={{
          position: 'absolute',
          top: 8,
          right: 8,
          border: 0,
          background: 'transparent',
          color: palette.textTertiary,
          cursor: 'pointer'
        }}
        aria-label="Dismiss"
      >
        ×
      </button>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ flex: 1 }}>{message}</span>
        {actionLabel && onAction ? (
          <Button size="small" onClick={onAction}>
            {actionLabel}
          </Button>
        ) : null}
      </div>
    </motion.div>
  );
};

export const Page = ({ children, style }) => (
  <div
    style={{
      maxWidth: LAYOUT.maxContent,
      margin: '0 auto',
      padding: `${SPACE.x24}px ${LAYOUT.gutter}px ${SPACE.x56}px`,
      minHeight: `calc(100vh - ${LAYOUT.navHeight}px)`,
      ...style
    }}
  >
    {children}
  </div>
);

export const PageHeader = ({ crumbs = [], title, subtitle, meta, actions, leading }) => {
  const palette = usePalette();
  return (
    <header style={{ marginBottom: SPACE.x24 }}>
      {leading ? <div style={{ marginBottom: SPACE.x8 }}>{leading}</div> : null}
      {crumbs.length > 0 ? (
        <nav aria-label="Breadcrumb" style={{ marginBottom: SPACE.x8, color: palette.textTertiary, fontSize: 12 }}>
          {crumbs.map((crumb, index) => (
            <span key={`${crumb.label}-${index}`}>
              {index > 0 ? <span style={{ margin: '0 6px', color: palette.lineStrong }}>/</span> : null}
              {crumb.to ? (
                <RouterLink to={crumb.to} style={{ color: palette.textTertiary, textDecoration: 'none' }}>
                  {crumb.label}
                </RouterLink>
              ) : (
                <span style={{ color: palette.textSecondary }}>{crumb.label}</span>
              )}
            </span>
          ))}
        </nav>
      ) : null}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: SPACE.x16,
          flexWrap: 'wrap'
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x12, flexWrap: 'wrap' }}>
            <h1 style={{ ...TYPE.h1, margin: 0, color: palette.text }}>{title}</h1>
            {meta}
          </div>
          {subtitle ? (
            <p style={{ ...TYPE.meta, color: palette.textSecondary, margin: `${SPACE.x4}px 0 0` }}>{subtitle}</p>
          ) : null}
        </div>
        {actions ? <div style={{ display: 'flex', gap: SPACE.x8, flexWrap: 'wrap' }}>{actions}</div> : null}
      </div>
    </header>
  );
};

export const Segmented = ({ value, onChange, options = [], layoutId }) => {
  const palette = usePalette();
  return (
    <div
      role="group"
      style={{
        display: 'inline-flex',
        height: 32,
        border: `1px solid ${palette.line}`,
        borderRadius: RADIUS.base,
        overflow: 'hidden',
        flexShrink: 0
      }}
    >
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={String(option.value)}
            type="button"
            aria-pressed={active}
            onClick={() => onChange?.(option.value)}
            style={{
              position: 'relative',
              height: 32,
              padding: '0 12px',
              border: 0,
              background: active ? palette.accentFill : 'transparent',
              color: active ? palette.accent : palette.textSecondary,
              fontFamily: FONTS.sans,
              fontSize: 13,
              fontWeight: 500,
              cursor: 'pointer',
              whiteSpace: 'nowrap'
            }}
          >
            {active && layoutId ? (
              <motion.span
                layoutId={layoutId}
                transition={TRANSITION.move}
                style={{
                  position: 'absolute',
                  left: 12,
                  right: 12,
                  bottom: 0,
                  height: 1,
                  background: palette.accent
                }}
              />
            ) : null}
            {option.label}
          </button>
        );
      })}
    </div>
  );
};

export const Toolbar = ({ children, style, nowrap = false }) => (
  <div
    style={{
      display: 'flex',
      flexWrap: nowrap ? 'nowrap' : 'wrap',
      alignItems: 'flex-end',
      gap: SPACE.x12,
      marginBottom: SPACE.x16,
      ...style
    }}
  >
    {children}
  </div>
);

export const Progress = ({ deferred = false }) => {
  const [visible, setVisible] = React.useState(!deferred);
  React.useEffect(() => {
    if (!deferred) {
      setVisible(true);
      return undefined;
    }
    const handle = window.setTimeout(() => setVisible(true), LOADING_DEFER_MS);
    return () => window.clearTimeout(handle);
  }, [deferred]);
  if (!visible) return null;
  return <LinearProgress />;
};
