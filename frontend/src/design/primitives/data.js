import React from 'react';
import { AnimatePresence, LayoutGroup, motion } from 'motion/react';
import { LAYOUT, RADIUS, ROW, SPACE, TYPE, STATUS_VOCABULARY, FONTS } from '../tokens';
import { LAYOUT_ID, TRANSITION, disclosureVariants, rowVariants } from '../motion';
import { usePalette } from '../usePalette';
import { Metric, Mono, Text } from './type';

export const SeverityRail = ({ severity = 'none' }) => {
  const palette = usePalette();
  const color = palette.severity[severity] || palette.severity.none;
  return (
    <span
      aria-hidden
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        bottom: 0,
        width: LAYOUT.railWidth,
        background: color
      }}
    />
  );
};

export const SeverityDot = ({ severity = 'none', size = 8 }) => {
  const palette = usePalette();
  const color = palette.severity[severity] || palette.severity.none;
  return (
    <span
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: RADIUS.round,
        background: color,
        display: 'inline-block',
        flexShrink: 0
      }}
    />
  );
};

const glyphColor = (palette, tone) => palette.tone[tone] || palette.textTertiary;

export const StatusGlyph = ({ status, label }) => {
  const palette = usePalette();
  const vocab = STATUS_VOCABULARY[String(status || '').toLowerCase()] || {
    label: String(status || 'Unknown'),
    glyph: 'dot',
    tone: 'muted'
  };
  const color = glyphColor(palette, vocab.tone);
  const size = 8;

  let mark = (
    <span style={{ width: size, height: size, borderRadius: RADIUS.round, background: color, display: 'inline-block' }} />
  );
  if (vocab.glyph === 'ring') {
    mark = (
      <span
        style={{
          width: size,
          height: size,
          borderRadius: RADIUS.round,
          border: `1.5px solid ${color}`,
          display: 'inline-block'
        }}
      />
    );
  } else if (vocab.glyph === 'half') {
    mark = (
      <span
        style={{
          width: size,
          height: size,
          borderRadius: RADIUS.round,
          background: `linear-gradient(90deg, ${color} 50%, transparent 50%)`,
          border: `1.5px solid ${color}`,
          display: 'inline-block',
          boxSizing: 'border-box'
        }}
      />
    );
  } else if (vocab.glyph === 'check') {
    mark = (
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
        <path d="M1.5 5.2 L3.8 7.5 L8.5 2.4" fill="none" stroke={color} strokeWidth="1.6" />
      </svg>
    );
  } else if (vocab.glyph === 'slash') {
    mark = (
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden>
        <circle cx="5" cy="5" r="3.5" fill="none" stroke={color} strokeWidth="1.4" />
        <path d="M2.4 7.6 L7.6 2.4" stroke={color} strokeWidth="1.4" />
      </svg>
    );
  }

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color, ...TYPE.micro }}>
      {mark}
      {label || vocab.label}
    </span>
  );
};

export const DataList = ({ children }) => {
  const palette = usePalette();
  return (
    <div style={{ borderTop: `1px solid ${palette.line}` }}>
      <LayoutGroup>{children}</LayoutGroup>
    </div>
  );
};

export const DataRow = ({
  id,
  severity,
  selected = false,
  expanded = false,
  onToggle,
  leading,
  title,
  meta,
  trailing,
  children
}) => {
  const palette = usePalette();
  return (
    <motion.div
      layout
      variants={rowVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      style={{
        position: 'relative',
        borderBottom: `1px solid ${palette.line}`,
        background: selected ? palette.accentFill : 'transparent'
      }}
    >
      {severity ? <SeverityRail severity={severity} /> : null}
      <div
        role={onToggle ? 'button' : undefined}
        tabIndex={onToggle ? 0 : undefined}
        onClick={onToggle}
        onKeyDown={(event) => {
          if (!onToggle) return;
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onToggle();
          }
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: SPACE.x12,
          minHeight: ROW.base,
          padding: `6px ${SPACE.x12}px 6px ${severity ? SPACE.x12 : SPACE.x8}px`,
          cursor: onToggle ? 'pointer' : 'default'
        }}
        onMouseEnter={(event) => {
          event.currentTarget.style.background = palette.hover;
        }}
        onMouseLeave={(event) => {
          event.currentTarget.style.background = selected ? palette.accentFill : 'transparent';
        }}
      >
        {leading}
        <div style={{ minWidth: 0, flex: 1 }}>
          {title}
          {meta}
        </div>
        {trailing}
      </div>
      <AnimatePresence initial={false}>
        {expanded && children ? (
          <motion.div
            key={`${id || 'row'}-body`}
            variants={disclosureVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            style={{ overflow: 'hidden', borderTop: `1px solid ${palette.line}` }}
          >
            <div style={{ padding: `${SPACE.x12}px ${SPACE.x12}px ${SPACE.x16}px ${SPACE.x16}px` }}>{children}</div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.div>
  );
};

export const MetricStrip = ({ items = [] }) => {
  const palette = usePalette();
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${Math.max(items.length, 1)}, minmax(0, 1fr))`,
        borderTop: `1px solid ${palette.line}`,
        borderBottom: `1px solid ${palette.line}`,
        marginBottom: SPACE.x24
      }}
    >
      {items.map((item, index) => (
        <button
          key={item.key || item.label}
          type="button"
          onClick={item.onClick}
          disabled={!item.onClick}
          style={{
            textAlign: 'left',
            background: 'transparent',
            border: 0,
            borderLeft: index === 0 ? 0 : `1px solid ${palette.line}`,
            padding: `${SPACE.x16}px ${SPACE.x16}px`,
            cursor: item.onClick ? 'pointer' : 'default',
            color: palette.text
          }}
        >
          <Text as="div" variant="micro" tone="tertiary">
            {item.label}
          </Text>
          <Metric value={item.value} style={{ marginTop: 4 }} />
          {item.hint ? (
            <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 4 }}>
              {item.hint}
            </Text>
          ) : null}
        </button>
      ))}
    </div>
  );
};

export const Tabs = ({ value, onChange, items = [] }) => {
  const palette = usePalette();
  return (
    <LayoutGroup>
      <div
        role="tablist"
        style={{
          display: 'flex',
          gap: SPACE.x4,
          borderBottom: `1px solid ${palette.line}`,
          marginBottom: SPACE.x16,
          overflowX: 'auto'
        }}
      >
        {items.map((item) => {
          const active = item.value === value;
          return (
            <button
              key={item.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onChange(item.value)}
              style={{
                position: 'relative',
                background: 'transparent',
                border: 0,
                color: active ? palette.text : palette.textSecondary,
                padding: '10px 12px',
                fontFamily: FONTS.sans,
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
            >
              {item.label}
              {active ? (
                <motion.span
                  layoutId={LAYOUT_ID.tabIndicator}
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
            </button>
          );
        })}
      </div>
    </LayoutGroup>
  );
};

export const Sparkline = ({ points = [], width = 120, height = 28 }) => {
  const palette = usePalette();
  if (!points.length) return null;
  const max = Math.max(...points, 1);
  const min = Math.min(...points, 0);
  const span = max - min || 1;
  const d = points
    .map((point, index) => {
      const x = (index / Math.max(points.length - 1, 1)) * width;
      const y = height - ((point - min) / span) * (height - 2) - 1;
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <motion.path
        d={d}
        fill="none"
        stroke={palette.accent}
        strokeWidth="1.5"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={TRANSITION.draw}
      />
    </svg>
  );
};

export const Bar = ({ value = 0, color }) => {
  const palette = usePalette();
  const width = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div style={{ height: 2, background: palette.line, width: '100%' }}>
      <motion.div
        initial={{ scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={TRANSITION.draw}
        style={{
          height: 2,
          width: `${width}%`,
          background: color || palette.accent,
          transformOrigin: 'left center'
        }}
      />
    </div>
  );
};

export const severityKeyFromScore = (score) => {
  const numeric = Number(score || 0);
  if (numeric >= 9) return 'critical';
  if (numeric >= 7) return 'high';
  if (numeric >= 4) return 'medium';
  if (numeric >= 0.1) return 'low';
  return 'none';
};

export { Mono };
