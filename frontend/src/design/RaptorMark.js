import React from 'react';
import { usePalette } from './usePalette';
import mark from '../brand/raptor-mark.png';
import markLight from '../brand/raptor-mark-light.png';
import wordmark from '../brand/raptor-wordmark.png';
import wordmarkLight from '../brand/raptor-wordmark-light.png';
import lockup from '../brand/raptor-lockup.png';
import lockupLight from '../brand/raptor-lockup-light.png';
import lockupPrint from '../brand/raptor-lockup-print.png';

const HEIGHT = {
  mark: 32,
  wordmark: 16,
  lockup: 192,
  lockupPrint: 36
};

/** Extra canvas margin so pointed tips are not flush with the clip edge. */
const SAFE = 0.04;

const RAW_FRAME = {
  mark: {
    light: { originX: 172 / 1254, originY: 259 / 1254, fillW: 914 / 1254, fillH: 677 / 1254, aspect: 1 },
    dark: { originX: 172 / 1254, originY: 259 / 1254, fillW: 914 / 1254, fillH: 677 / 1254, aspect: 1 }
  },
  wordmark: {
    light: { originX: 256 / 2172, originY: 289 / 724, fillW: 1669 / 2172, fillH: 173 / 724, aspect: 2172 / 724 },
    dark: { originX: 256 / 2172, originY: 289 / 724, fillW: 1669 / 2172, fillH: 173 / 724, aspect: 2172 / 724 }
  },
  lockup: {
    light: { originX: 178 / 1254, originY: 260 / 1254, fillW: 899 / 1254, fillH: 699 / 1254, aspect: 1 },
    dark: { originX: 178 / 1254, originY: 260 / 1254, fillW: 899 / 1254, fillH: 699 / 1254, aspect: 1 }
  },
  lockupPrint: {
    light: { originX: 97 / 1254, originY: 211 / 1254, fillW: 1061 / 1254, fillH: 835 / 1254, aspect: 1 },
    dark: { originX: 97 / 1254, originY: 211 / 1254, fillW: 1061 / 1254, fillH: 835 / 1254, aspect: 1 }
  }
};

const padFrame = (frame) => {
  const originX = Math.max(0, frame.originX - SAFE);
  const originY = Math.max(0, frame.originY - SAFE);
  return {
    originX,
    originY,
    fillW: Math.min(1 - originX, frame.fillW + SAFE * 2),
    fillH: Math.min(1 - originY, frame.fillH + SAFE * 2),
    aspect: frame.aspect
  };
};

const FRAME = {
  mark: { light: padFrame(RAW_FRAME.mark.light), dark: padFrame(RAW_FRAME.mark.dark) },
  wordmark: { light: padFrame(RAW_FRAME.wordmark.light), dark: padFrame(RAW_FRAME.wordmark.dark) },
  lockup: { light: padFrame(RAW_FRAME.lockup.light), dark: padFrame(RAW_FRAME.lockup.dark) },
  lockupPrint: { light: padFrame(RAW_FRAME.lockupPrint.light), dark: padFrame(RAW_FRAME.lockupPrint.dark) }
};

export const RAPTOR_BRAND = {
  mark,
  markLight,
  wordmark,
  wordmarkLight,
  lockup,
  lockupLight,
  lockupPrint
};

export const raptorBrandSrc = (variant, mode = 'dark') => {
  const light = mode === 'light';
  if (variant === 'wordmark') return light ? wordmarkLight : wordmark;
  if (variant === 'lockup') return light ? lockupLight : lockup;
  if (variant === 'lockupPrint') return lockupPrint;
  return light ? markLight : mark;
};

/**
 * RAPTOR brand mark.
 *   mark        — wings, navbar / compact chrome
 *   wordmark    — RAPTOR with chevron A
 *   lockup      — stacked icon + wordmark (login)
 *   lockupPrint — light lockup for report paper
 */
export const RaptorMark = ({
  variant = 'mark',
  height,
  width,
  alt = 'RAPTOR',
  decorative = false,
  style
}) => {
  const palette = usePalette();
  const src = raptorBrandSrc(variant, palette.mode);
  const resolvedHeight = height || HEIGHT[variant] || HEIGHT.mark;
  const frame = FRAME[variant]?.[palette.mode] || FRAME.mark[palette.mode];
  const imgHeight = resolvedHeight / frame.fillH;
  const imgWidth = imgHeight * frame.aspect;
  const boxWidth = width || resolvedHeight * (frame.fillW / frame.fillH) * frame.aspect;
  const knockOutPlate = palette.mode === 'dark';
  const blendPlate = knockOutPlate ? 'screen' : 'multiply';
  const { maxWidth, ...restStyle } = style || {};
  return (
    <span
      style={{
        position: 'relative',
        display: 'block',
        height: resolvedHeight,
        width: boxWidth,
        maxWidth,
        overflow: 'hidden',
        flexShrink: 0,
        minWidth: 0,
        minHeight: 0,
        lineHeight: 0
      }}
    >
      <img
        src={src}
        alt={decorative ? '' : alt}
        aria-hidden={decorative ? true : undefined}
        draggable="false"
        style={{
          position: 'absolute',
          top: -frame.originY * imgHeight,
          left: -frame.originX * imgWidth,
          height: imgHeight,
          width: imgWidth,
          maxWidth: 'none',
          display: 'block',
          objectFit: 'fill',
          userSelect: 'none',
          mixBlendMode: blendPlate,
          ...restStyle
        }}
      />
    </span>
  );
};

export default RaptorMark;
