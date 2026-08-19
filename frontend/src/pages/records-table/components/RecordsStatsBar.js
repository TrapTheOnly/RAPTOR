import React from 'react';
import { Metric, Text } from '../../../design/primitives';
import { LAYOUT_ID, TRANSITION } from '../../../design/motion';
import { SPACE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import { motion } from 'motion/react';

const RecordsStatsBar = ({
  stats,
  inventoryCount,
  totalCount,
  statusFilter,
  conflictFilter,
  onStatusFilterChange,
  onConflictFilterChange
}) => {
  const palette = usePalette();
  const filtered = inventoryCount !== totalCount;
  const selected = conflictFilter ? 'conflicts' : statusFilter === 'missing' ? 'missing' : 'hosts';

  const items = [
    {
      key: 'hosts',
      label: 'Hosts',
      value: inventoryCount,
      hint: filtered ? `of ${totalCount}` : undefined,
      onClick: () => {
        onStatusFilterChange('');
        onConflictFilterChange(false);
      }
    },
    {
      key: 'missing',
      label: 'Missing',
      value: stats.missing,
      onClick: () => {
        onConflictFilterChange(false);
        onStatusFilterChange(statusFilter === 'missing' ? '' : 'missing');
      }
    },
    {
      key: 'conflicts',
      label: 'Conflicts',
      value: stats.conflicts,
      onClick: () => {
        onStatusFilterChange('');
        onConflictFilterChange(!conflictFilter);
      }
    }
  ];

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${items.length}, minmax(0, 1fr))`,
        borderTop: `1px solid ${palette.line}`,
        borderBottom: `1px solid ${palette.line}`,
        marginBottom: SPACE.x16
      }}
    >
      {items.map((item, index) => (
        <button
          key={item.key}
          type="button"
          onClick={item.onClick}
          style={{
            position: 'relative',
            textAlign: 'left',
            background: 'transparent',
            border: 0,
            borderLeft: index === 0 ? 0 : `1px solid ${palette.line}`,
            padding: `${SPACE.x16}px ${SPACE.x16}px`,
            cursor: 'pointer',
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
          {selected === item.key ? (
            <motion.span
              layoutId={LAYOUT_ID.recordsKpi}
              transition={TRANSITION.move}
              style={{
                position: 'absolute',
                left: 16,
                right: 16,
                bottom: 0,
                height: 1,
                background: palette.accent
              }}
            />
          ) : null}
        </button>
      ))}
    </div>
  );
};

export default RecordsStatsBar;
