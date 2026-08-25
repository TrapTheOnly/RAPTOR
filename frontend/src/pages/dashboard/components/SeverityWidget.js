import React from 'react';
import { Bar, Mono, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import { SEVERITY_ORDER } from '../constants';
import { WidgetCard } from './ArrangeGrid';

const SeverityWidget = ({
  bySeverity = {},
  arranging,
  span,
  onSpanChange,
  dragControls,
  onSelect
}) => {
  const palette = usePalette();
  const items = SEVERITY_ORDER.map((item) => ({
    ...item,
    value: Number(bySeverity[item.key] || 0)
  }));
  const max = Math.max(...items.map((item) => item.value), 0);
  const total = items.reduce((sum, item) => sum + item.value, 0);

  return (
    <WidgetCard
      title="Open by severity"
      hint="Live open findings. Drafts are excluded."
      arranging={arranging}
      span={span}
      onSpanChange={onSpanChange}
      dragControls={dragControls}
    >
      {total === 0 ? (
        <Text variant="meta" tone="secondary">
          No open findings.
        </Text>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => onSelect?.(item.key)}
              disabled={!onSelect || arranging}
              style={{
                background: 'transparent',
                border: 0,
                padding: 0,
                textAlign: 'left',
                cursor: onSelect ? 'pointer' : 'default',
                color: 'inherit'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                <Text variant="meta">{item.label}</Text>
                <Mono tone="secondary">{item.value}</Mono>
              </div>
              <Bar
                value={max > 0 ? (item.value / max) * 100 : 0}
                color={palette.severity?.[item.key] || palette.accent}
              />
            </button>
          ))}
        </div>
      )}
      <Text variant="meta" tone="secondary" style={{ marginTop: SPACE.x12 }}>
        {total} open
      </Text>
    </WidgetCard>
  );
};

export default SeverityWidget;
