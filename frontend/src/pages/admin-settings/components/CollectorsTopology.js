import React, { useMemo } from 'react';
import { Button, Mono, Text } from '../../../design/primitives';
import { FONTS, RADIUS, SPACE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';

const HUB_X = 120;
const AGENT_X = 520;
const TOP = 36;
const ROW = 72;
const HUB_W = 140;
const HUB_H = 88;
const AGENT_W = 210;
const AGENT_H = 56;

const Pager = ({ page, pageCount, onPageChange }) => {
  if (pageCount <= 1) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8, marginTop: SPACE.x8 }}>
      <Button size="small" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        Previous
      </Button>
      <Mono>
        {page} / {pageCount}
      </Mono>
      <Button size="small" disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>
        Next
      </Button>
    </div>
  );
};

const CollectorsTopology = ({ agents, page, pageCount, onPageChange }) => {
  const palette = usePalette();
  const height = Math.max(220, TOP * 2 + Math.max(agents.length, 1) * ROW);
  const hubY = height / 2 - HUB_H / 2;

  const layout = useMemo(
    () =>
      agents.map((agent, index) => {
        const y = TOP + index * ROW;
        const midX = (HUB_X + HUB_W + AGENT_X) / 2;
        const hubCy = hubY + HUB_H / 2;
        const agentCy = y + AGENT_H / 2;
        const d = `M ${HUB_X + HUB_W} ${hubCy} H ${midX} V ${agentCy} H ${AGENT_X}`;
        return { agent, y, d };
      }),
    [agents, hubY]
  );

  return (
    <div>
      <Text as="div" variant="bodyStrong" style={{ marginBottom: SPACE.x8 }}>
        Agent fabric
      </Text>
      <div
        style={{
          overflowX: 'hidden',
          border: `1px solid ${palette.line}`,
          borderRadius: RADIUS.base,
          background: palette.canvas
        }}
      >
        <svg
          viewBox={`0 0 760 ${height}`}
          width={760}
          height={height}
          preserveAspectRatio="xMinYMid meet"
          role="img"
          aria-label="Collector topology"
          style={{ width: '100%', maxWidth: 760, height: 'auto', display: 'block' }}
        >
          {layout.map(({ agent, d }) => (
            <g key={`pipe-${agent.id}`}>
              <path
                d={d}
                fill="none"
                stroke={agent.online ? palette.accent : palette.lineStrong}
                strokeWidth="2"
                strokeLinejoin="miter"
                strokeLinecap="square"
              />
              {agent.ingesting ? (
                <circle r="4" fill={palette.lifecycle.positive}>
                  <animateMotion dur="1.8s" repeatCount="indefinite" path={d} />
                </circle>
              ) : null}
            </g>
          ))}
          <rect
            x={HUB_X}
            y={hubY}
            width={HUB_W}
            height={HUB_H}
            rx={RADIUS.panel}
            fill={palette.raised}
            stroke={palette.lineStrong}
          />
          <text
            x={HUB_X + HUB_W / 2}
            y={hubY + 38}
            textAnchor="middle"
            fill={palette.text}
            fontSize="14"
            fontWeight="600"
            fontFamily={FONTS.sans}
          >
            RAPTOR
          </text>
          <text
            x={HUB_X + HUB_W / 2}
            y={hubY + 58}
            textAnchor="middle"
            fill={palette.textSecondary}
            fontSize="11"
            fontFamily={FONTS.mono}
          >
            ingest hub
          </text>
          {layout.map(({ agent, y }) => (
            <g key={`node-${agent.id}`}>
              <rect
                x={AGENT_X}
                y={y}
                width={AGENT_W}
                height={AGENT_H}
                rx={RADIUS.panel}
                fill={palette.raised}
                stroke={agent.online ? palette.accent : palette.lineStrong}
              />
              <text
                x={AGENT_X + 12}
                y={y + 24}
                fill={palette.text}
                fontSize="13"
                fontWeight="600"
                fontFamily={FONTS.sans}
              >
                {(agent.display_name || agent.hostname || '').slice(0, 22)}
              </text>
              <text
                x={AGENT_X + 12}
                y={y + 42}
                fill={palette.textSecondary}
                fontSize="11"
                fontFamily={FONTS.mono}
              >
                {agent.mode === 'two_sided' ? 'two-sided' : 'one-sided'}
                {agent.online ? ' · live' : ' · idle'}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <Pager page={page} pageCount={pageCount} onPageChange={onPageChange} />
    </div>
  );
};

export default CollectorsTopology;
