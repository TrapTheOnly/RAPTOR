import React, { useEffect, useRef } from 'react';
import { animate, motion, useMotionValue, useTransform } from 'motion/react';
import { FONTS, TYPE } from '../tokens';
import { TRANSITION } from '../motion';
import { usePalette } from '../usePalette';

const VARIANT_MAP = {
  display: TYPE.display,
  h1: TYPE.h1,
  h2: TYPE.h2,
  eyebrow: TYPE.eyebrow,
  body: TYPE.body,
  bodyStrong: TYPE.bodyStrong,
  meta: TYPE.meta,
  micro: TYPE.micro,
  metric: TYPE.metric
};

const toneColor = (palette, tone) => {
  if (tone === 'secondary') return palette.textSecondary;
  if (tone === 'tertiary') return palette.textTertiary;
  if (tone === 'accent') return palette.accent;
  if (palette.tone[tone]) return palette.tone[tone];
  return palette.text;
};

export const Text = ({
  as: Tag = 'span',
  variant = 'body',
  tone = 'primary',
  style,
  children,
  ...rest
}) => {
  const palette = usePalette();
  return (
    <Tag
      style={{
        margin: 0,
        color: toneColor(palette, tone),
        fontFamily: FONTS.sans,
        ...VARIANT_MAP[variant],
        ...style
      }}
      {...rest}
    >
      {children}
    </Tag>
  );
};

export const Mono = ({ as: Tag = 'span', tone = 'primary', style, children, ...rest }) => {
  const palette = usePalette();
  return (
    <Tag
      style={{
        margin: 0,
        color: toneColor(palette, tone),
        fontFamily: FONTS.mono,
        fontSize: 13,
        lineHeight: '20px',
        fontVariantNumeric: 'tabular-nums',
        letterSpacing: '-0.01em',
        ...style
      }}
      {...rest}
    >
      {children}
    </Tag>
  );
};

const parseNumeric = (value) => {
  if (typeof value === 'number' && Number.isFinite(value)) return { number: value, prefix: '', suffix: '' };
  const raw = String(value ?? '');
  const match = raw.match(/^([^0-9.-]*)(-?\d+(?:\.\d+)?)(.*)$/);
  if (!match) return null;
  return { number: Number(match[2]), prefix: match[1], suffix: match[3] };
};

export const Metric = ({ value, style }) => {
  const parsed = parseNumeric(value);
  const numericValue = parsed ? parsed.number : null;
  const source = useMotionValue(0);
  const decimals = parsed && String(parsed.number).includes('.') ? 1 : 0;
  const display = useTransform(source, (latest) => {
    if (!parsed) return String(value ?? '');
    return `${parsed.prefix}${latest.toFixed(decimals)}${parsed.suffix}`;
  });
  const targetRef = useRef(null);
  const controlsRef = useRef(null);

  useEffect(() => {
    if (numericValue === null) return undefined;
    if (targetRef.current === numericValue) return undefined;
    targetRef.current = numericValue;
    controlsRef.current?.stop();
    controlsRef.current = animate(source, numericValue, TRANSITION.value);
    return undefined;
  }, [numericValue, source]);

  return (
    <motion.span
      style={{
        ...TYPE.metric,
        color: 'var(--raptor-text)',
        display: 'block',
        fontVariantNumeric: 'tabular-nums',
        ...style
      }}
    >
      {parsed ? display : String(value ?? '')}
    </motion.span>
  );
};
