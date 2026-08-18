import React, { useMemo } from 'react';
import { Box, Pagination, Typography } from '@mui/material';

const HUB_X = 120;
const AGENT_X = 520;
const TOP = 36;
const ROW = 72;
const HUB_W = 140;
const HUB_H = 88;
const AGENT_W = 210;
const AGENT_H = 56;

const CollectorsTopology = ({ agents, page, pageCount, onPageChange }) => {
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
    <Box>
      <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
        Agent fabric
      </Typography>
      <Box
        sx={{
          overflowX: 'hidden',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          bgcolor: 'background.default',
          '& svg': { width: '100%', maxWidth: 760, height: 'auto', display: 'block' }
        }}
      >
        <svg
          viewBox={`0 0 760 ${height}`}
          width={760}
          height={height}
          preserveAspectRatio="xMinYMid meet"
          role="img"
          aria-label="Collector topology"
        >
          <defs>
            <filter id="pipe-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="1.2" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          {layout.map(({ agent, d }) => (
            <g key={`pipe-${agent.id}`}>
              <path
                d={d}
                fill="none"
                stroke={agent.online ? '#5c6bc0' : '#90a4ae'}
                strokeWidth="4"
                strokeLinejoin="miter"
                strokeLinecap="square"
                filter="url(#pipe-glow)"
              />
              {agent.ingesting ? (
                <circle r="5" fill="#26a69a">
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
            rx="6"
            fill="#1565c0"
          />
          <text
            x={HUB_X + HUB_W / 2}
            y={hubY + 38}
            textAnchor="middle"
            fill="#fff"
            fontSize="14"
            fontWeight="700"
          >
            RAPTOR
          </text>
          <text
            x={HUB_X + HUB_W / 2}
            y={hubY + 58}
            textAnchor="middle"
            fill="#bbdefb"
            fontSize="11"
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
                rx="6"
                fill={agent.online ? '#1b5e20' : '#455a64'}
              />
              <text
                x={AGENT_X + 12}
                y={y + 24}
                fill="#fff"
                fontSize="13"
                fontWeight="700"
              >
                {(agent.display_name || agent.hostname || '').slice(0, 22)}
              </text>
              <text x={AGENT_X + 12} y={y + 42} fill="#c8e6c9" fontSize="11">
                {agent.mode === 'two_sided' ? 'two-sided' : 'one-sided'}
                {agent.online ? ' · live' : ' · idle'}
              </text>
            </g>
          ))}
        </svg>
      </Box>
      {pageCount > 1 ? (
        <Pagination
          sx={{ mt: 1 }}
          count={pageCount}
          page={page}
          onChange={(_, value) => onPageChange(value)}
          size="small"
        />
      ) : null}
    </Box>
  );
};

export default CollectorsTopology;
