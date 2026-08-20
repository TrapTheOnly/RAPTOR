import React, { useMemo, useState } from 'react';
import { LineChart, Mono, Segmented, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import { DEFAULT_TREND_WINDOW, sliceWeekly } from '../layout';
import { WidgetCard } from './ArrangeGrid';

const WINDOW_OPTIONS = [
  { value: '4w', label: '4w' },
  { value: '12w', label: '12w' },
  { value: '6m', label: '6m' }
];

const TrendWidget = ({ weekly = [], arranging, span, onSpanChange, dragControls }) => {
  const palette = usePalette();
  const [windowKey, setWindowKey] = useState(DEFAULT_TREND_WINDOW);
  const rows = useMemo(() => sliceWeekly(weekly, windowKey), [weekly, windowKey]);
  const labels = rows.map((row) => row.label);
  const hasFlow = rows.some((row) => Number(row.opened || 0) + Number(row.closed || 0) > 0);
  const hasActive = rows.some((row) => Number(row.openStock || 0) > 0);

  return (
    <WidgetCard
      title="Opened vs closed"
      hint="Weekly flow, then currently active stock. Hover a week for counts."
      arranging={arranging}
      span={span}
      onSpanChange={onSpanChange}
      dragControls={dragControls}
      actions={
        <Segmented value={windowKey} onChange={setWindowKey} options={WINDOW_OPTIONS} />
      }
    >
      {hasFlow ? (
        <LineChart
          ariaLabel="Opened and closed findings over time. Hover a week to read the counts."
          tooltipTitle={(hover) => `Week of ${hover.label}`}
          footer={(hover) => {
            const opened = hover.values.find((item) => item.key === 'opened')?.value || 0;
            const closed = hover.values.find((item) => item.key === 'closed')?.value || 0;
            return (
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 16,
                  marginTop: 4,
                  paddingTop: 4
                }}
              >
                <Text variant="meta" tone="secondary">
                  Net
                </Text>
                <Mono>{opened - closed}</Mono>
              </div>
            );
          }}
          series={[
            {
              key: 'opened',
              label: 'Opened',
              color: palette.severity?.high || palette.accent,
              points: rows.map((row) => Number(row.opened || 0)),
              labels
            },
            {
              key: 'closed',
              label: 'Closed',
              color: palette.lifecycle?.positive || palette.accent,
              points: rows.map((row) => Number(row.closed || 0)),
              labels
            }
          ]}
        />
      ) : (
        <Text variant="meta" tone="secondary">
          No findings yet to plot over time.
        </Text>
      )}

      <div style={{ marginTop: SPACE.x24 }}>
        <Text as="div" variant="h2">
          Currently active
        </Text>
        <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 12px' }}>
          Open findings still live at the end of each week.
        </Text>
        {hasActive || hasFlow ? (
          <LineChart
            height={160}
            ariaLabel="Currently active findings over time. Hover a week to read the count."
            tooltipTitle={(hover) => `Week of ${hover.label}`}
            series={[
              {
                key: 'active',
                label: 'Active',
                color: palette.severity?.critical || palette.accent,
                points: rows.map((row) => Number(row.openStock || 0)),
                labels
              }
            ]}
          />
        ) : (
          <Text variant="meta" tone="secondary">
            No active findings in this window.
          </Text>
        )}
      </div>
    </WidgetCard>
  );
};

export default TrendWidget;
