import React, { useEffect, useId, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { RADIUS } from '../tokens';
import { TRANSITION, panelVariants } from '../motion';
import { usePalette } from '../usePalette';
import { Mono, Text } from './type';

const LineChart = ({
  series = [],
  height = 180,
  empty = 'No data yet to plot over time.',
  ariaLabel = 'Line chart. Hover a point to read the counts.',
  tooltipTitle,
  footer
}) => {
  const palette = usePalette();
  const wrapRef = useRef(null);
  const [width, setWidth] = useState(0);
  const [hoverIndex, setHoverIndex] = useState(null);
  const clipId = useId().replace(/:/g, '');

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return undefined;
    const apply = () => {
      const next = Math.round(node.getBoundingClientRect().width);
      if (next > 0) setWidth(next);
    };
    apply();
    if (typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver(apply);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const n = series[0]?.points?.length || 0;
  const labels = series[0]?.labels || [];
  const plotWidth = width > 0 ? width : 520;
  if (!n) {
    return (
      <Text variant="meta" tone="secondary">
        {empty}
      </Text>
    );
  }

  const values = series.flatMap((item) => (item.points || []).map((point) => Number(point) || 0));
  const max = Math.max(...values, 1);
  const pad = { top: 8, right: 8, bottom: 24, left: 28 };
  const innerW = plotWidth - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const xAt = (index) => pad.left + (n === 1 ? innerW / 2 : (index / (n - 1)) * innerW);
  const yAt = (value) => pad.top + innerH - (Number(value) / max) * innerH;

  const paths = series.map((item) => {
    const values = (item.points || []).map((point) => Number(point) || 0);
    const plotted = values.map((value, index) => ({ x: xAt(index), y: yAt(value) }));
    const d = plotted.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x} ${point.y}`).join(' ');
    return { key: item.key, label: item.label, color: item.color, values, plotted, d };
  });

  const pickIndex = (event) => {
    const svg = event.currentTarget;
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const x = ((event.clientX - rect.left) / rect.width) * plotWidth;
    const t = n === 1 ? 0 : (x - pad.left) / innerW;
    const index = Math.round(t * Math.max(n - 1, 1));
    setHoverIndex(Math.max(0, Math.min(n - 1, index)));
  };

  const hover =
    hoverIndex == null
      ? null
      : {
          index: hoverIndex,
          label: labels[hoverIndex],
          x: xAt(hoverIndex),
          values: paths.map((item) => ({
            key: item.key,
            label: item.label,
            color: item.color,
            value: Number(item.values[hoverIndex] || 0),
            y: item.plotted[hoverIndex]?.y ?? yAt(0)
          }))
        };

  const flipLeft = Boolean(
    hover && (hover.index >= Math.max(0, n - 3) || hover.x > plotWidth - 172)
  );
  const tipLeft = hover ? (flipLeft ? 'auto' : hover.x) : 0;
  const tipRight = hover && flipLeft ? Math.max(8, plotWidth - hover.x) : 'auto';
  const tipTransform = hover ? (flipLeft ? 'translate(0, 0)' : hover.x < 72 ? 'translate(0, 0)' : 'translate(-50%, 0)') : undefined;

  return (
    <div ref={wrapRef} style={{ width: '100%', position: 'relative', overflow: 'visible' }}>
      <svg
        width="100%"
        height={height}
        viewBox={`0 0 ${plotWidth} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={ariaLabel}
        style={{ display: 'block', width: '100%', cursor: 'crosshair' }}
        onMouseMove={pickIndex}
        onMouseLeave={() => setHoverIndex(null)}
      >
        <defs>
          <clipPath id={clipId}>
            <motion.rect
              x={pad.left}
              y={0}
              height={height}
              initial={{ width: 0 }}
              animate={{ width: innerW }}
              transition={TRANSITION.draw}
            />
          </clipPath>
        </defs>
        {[0, 0.5, 1].map((frac) => {
          const y = yAt(max * frac);
          return (
            <g key={frac}>
              <line x1={pad.left} x2={plotWidth - pad.right} y1={y} y2={y} stroke={palette.line} strokeWidth="1" />
              <text x={pad.left - 6} y={y + 4} textAnchor="end" fill={palette.textTertiary} fontSize="10">
                {Math.round(max * frac)}
              </text>
            </g>
          );
        })}
        <g clipPath={`url(#${clipId})`}>
          {paths.map((item) => (
            <motion.path
              key={item.key}
              d={item.d}
              fill="none"
              stroke={item.color}
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={TRANSITION.draw}
            />
          ))}
        </g>
        {labels.map((label, index) =>
          index % 2 === 0 || n < 8 ? (
            <text
              key={`${label}-${index}`}
              x={xAt(index)}
              y={height - 6}
              textAnchor="middle"
              fill={hoverIndex === index ? palette.text : palette.textTertiary}
              fontSize="10"
              fontWeight={hoverIndex === index ? 600 : 400}
            >
              {label}
            </text>
          ) : null
        )}
        <AnimatePresence>
          {hover ? (
            <motion.g
              key="cursor"
              initial={{ opacity: 0, x: hover.x }}
              animate={{ opacity: 1, x: hover.x }}
              exit={{ opacity: 0 }}
              transition={TRANSITION.move}
              style={{ pointerEvents: 'none' }}
            >
              <line x1={0} x2={0} y1={pad.top} y2={pad.top + innerH} stroke={palette.accent} strokeWidth="1" />
              {hover.values.map((item) => (
                <circle
                  key={item.key}
                  cx={0}
                  cy={item.y}
                  r={3.5}
                  fill={item.color}
                  stroke={palette.surface}
                  strokeWidth="1.5"
                />
              ))}
            </motion.g>
          ) : null}
        </AnimatePresence>
        <rect x={pad.left} y={pad.top} width={innerW} height={innerH} fill="transparent" />
      </svg>
      <AnimatePresence>
        {hover ? (
          <motion.div
            key="tip"
            variants={panelVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            style={{
              position: 'absolute',
              left: tipLeft,
              right: tipRight,
              top: pad.top,
              transform: tipTransform,
              minWidth: 148,
              maxWidth: 220,
              padding: '8px 10px',
              background: palette.raised,
              border: `1px solid ${palette.line}`,
              borderRadius: RADIUS.base,
              pointerEvents: 'none',
              zIndex: 2
            }}
            data-align={flipLeft ? 'left' : 'center'}
            role="status"
          >
            <Text as="div" variant="meta" tone="secondary" style={{ marginBottom: 6 }}>
              {tooltipTitle ? tooltipTitle(hover) : hover.label}
            </Text>
            {hover.values.map((item) => (
              <div
                key={item.key}
                style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'center' }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 8, height: 8, background: item.color, display: 'inline-block' }} />
                  <Text variant="meta">{item.label}</Text>
                </span>
                <Mono>{item.value}</Mono>
              </div>
            ))}
            {footer ? footer(hover) : null}
          </motion.div>
        ) : null}
      </AnimatePresence>
      <div style={{ display: 'flex', gap: 16, marginTop: 4 }}>
        {series.map((item) => (
          <span key={item.key} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, background: item.color, display: 'inline-block' }} />
            <Text variant="meta" tone="secondary">
              {item.label}
            </Text>
          </span>
        ))}
      </div>
    </div>
  );
};

export { LineChart };
