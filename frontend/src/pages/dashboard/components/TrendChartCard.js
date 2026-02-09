import React from 'react';
import { Box, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';

const CHART_WIDTH = 760;
const CHART_HEIGHT = 240;
const CHART_PADDING = { top: 20, right: 12, bottom: 36, left: 12 };

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const TrendChartCard = ({ title, subtitle, labels, series }) => {
  const seriesValues = series.flatMap((entry) => entry.data || []);
  const maxValue = Math.max(1, ...seriesValues);
  const innerWidth = CHART_WIDTH - CHART_PADDING.left - CHART_PADDING.right;
  const innerHeight = CHART_HEIGHT - CHART_PADDING.top - CHART_PADDING.bottom;

  const getPoints = (values) =>
    values.map((value, index) => {
      const x =
        labels.length > 1
          ? CHART_PADDING.left + (index / (labels.length - 1)) * innerWidth
          : CHART_PADDING.left + innerWidth / 2;
      const y =
        CHART_PADDING.top +
        innerHeight -
        (clamp(value, 0, maxValue) / maxValue) * innerHeight;
      return { x, y };
    });

  const getPathFromPoints = (points) =>
    points
      .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
      .join(' ');

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          {title}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 1.25 }}>
          {subtitle}
        </Typography>

        <Stack direction="row" spacing={0.75} sx={{ mb: 1.5 }} useFlexGap flexWrap="wrap">
          {series.map((entry) => (
            <Chip
              key={entry.key}
              size="small"
              label={entry.label}
              sx={{
                color: entry.color,
                fontWeight: 600,
                border: `1px solid ${alpha(entry.color, 0.35)}`,
                backgroundColor: alpha(entry.color, 0.1)
              }}
            />
          ))}
        </Stack>

        <Box sx={{ width: '100%', overflowX: 'auto' }}>
          <svg
            width="100%"
            viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
            role="img"
            aria-label={title}
          >
            {[0, 1, 2, 3, 4].map((lineIndex) => {
              const y = CHART_PADDING.top + (lineIndex / 4) * innerHeight;
              return (
                <line
                  key={`grid-${lineIndex}`}
                  x1={CHART_PADDING.left}
                  x2={CHART_WIDTH - CHART_PADDING.right}
                  y1={y}
                  y2={y}
                  stroke="currentColor"
                  opacity={0.12}
                />
              );
            })}

            {series.map((entry) => {
              const points = getPoints(entry.data || []);
              const path = getPathFromPoints(points);
              return (
                <g key={entry.key}>
                  <path
                    d={path}
                    fill="none"
                    stroke={entry.color}
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  {points.map((point, index) => (
                    <circle
                      key={`${entry.key}-${index}`}
                      cx={point.x}
                      cy={point.y}
                      r="3.5"
                      fill={entry.color}
                    />
                  ))}
                </g>
              );
            })}

            {labels.map((label, index) => {
              const x =
                labels.length > 1
                  ? CHART_PADDING.left + (index / (labels.length - 1)) * innerWidth
                  : CHART_PADDING.left + innerWidth / 2;
              return (
                <text
                  key={`label-${label}-${index}`}
                  x={x}
                  y={CHART_HEIGHT - 12}
                  textAnchor="middle"
                  fontSize="12"
                  fill="currentColor"
                  opacity={0.72}
                >
                  {label}
                </text>
              );
            })}
          </svg>
        </Box>
      </CardContent>
    </Card>
  );
};

export default TrendChartCard;
