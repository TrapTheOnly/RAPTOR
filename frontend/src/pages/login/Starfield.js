import React, { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';

const FIELD = 120;
/** Four-point sparkle (not a diamond): pinched waist on the N/E/S/W axes. */
const SPARKLE =
  'M8 0 L9.15 6.15 L16 8 L9.15 9.85 L8 16 L6.85 9.85 L0 8 L6.85 6.15 Z';

const mulberry = (seed) => {
  let t = seed + 0x6d2b79f5;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};

const buildStars = (count) => {
  const stars = [];
  for (let i = 0; i < count; i += 1) {
    stars.push({
      id: i,
      x: mulberry(i * 19 + 3) * FIELD,
      y: mulberry(i * 47 + 11) * FIELD,
      size: 0.02 + mulberry(i * 31 + 7) * 0.03,
      delay: mulberry(i * 13 + 5) * 4.8,
      duration: 2.6 + mulberry(i * 23 + 17) * 3.8,
      accent: mulberry(i * 41 + 29) > 0.91
    });
  }
  return stars;
};

const randomPop = () => ({
  id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
  x: 6 + Math.random() * (FIELD - 12),
  y: 6 + Math.random() * (FIELD - 12),
  size: 0.034 + Math.random() * 0.02,
});

const Sparkle = ({ x, y, size, fill, style }) => (
  <g transform={`translate(${x} ${y}) scale(${size})`} style={style}>
    <path d={SPARKLE} fill={fill} transform="translate(-8 -8)" />
  </g>
);

const Starfield = ({ color = '#F4F7FB', accent = '#35D6E8' }) => {
  const reduced = useReducedMotion();
  const stars = useMemo(() => buildStars(160), []);
  const [pops, setPops] = useState(() => [randomPop(), randomPop()]);

  useEffect(() => {
    if (reduced) return undefined;
    const id = window.setInterval(() => {
      setPops((prev) => {
        const next = prev.slice();
        next[Math.floor(Math.random() * next.length)] = randomPop();
        return next;
      });
    }, 900);
    return () => window.clearInterval(id);
  }, [reduced]);

  return (
    <svg
      aria-hidden
      viewBox={`0 0 ${FIELD} ${FIELD}`}
      preserveAspectRatio="xMidYMid slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
    >
      <defs>
        <style>
          {`
            @keyframes raptorStarTwinkle {
              0% { opacity: 0; }
              10% { opacity: 0.95; }
              55% { opacity: 0.18; }
              100% { opacity: 0.12; }
            }
          `}
        </style>
      </defs>
      {stars.map((star) => (
        <Sparkle
          key={star.id}
          x={star.x}
          y={star.y}
          size={star.size}
          fill={star.accent ? accent : color}
          style={{
            opacity: reduced ? 0.4 : 0,
            animation: reduced
              ? 'none'
              : `raptorStarTwinkle ${star.duration}s ease-in-out ${star.delay}s infinite backwards`
          }}
        />
      ))}
      <AnimatePresence>
        {reduced
          ? null
          : pops.map((pop) => (
              <motion.g
                key={pop.id}
                initial={{ opacity: 0, scale: 0.2 }}
                animate={{ opacity: [0, 1, 0.45, 0], scale: [0.4, 1.08, 1, 0.5] }}
                exit={{ opacity: 0 }}
                transition={{ duration: 1.25, ease: 'easeOut' }}
                style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
              >
                <Sparkle x={pop.x} y={pop.y} size={pop.size} fill={color} />
              </motion.g>
            ))}
      </AnimatePresence>
    </svg>
  );
};

export default Starfield;
