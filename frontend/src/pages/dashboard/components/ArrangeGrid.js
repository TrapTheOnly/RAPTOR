import React from 'react';
import { Reorder, useDragControls } from 'motion/react';
import { DragIndicator } from '@mui/icons-material';
import { Segmented, Surface, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';

export const WidgetCard = ({
  title,
  hint,
  actions,
  arranging = false,
  span = 'half',
  onSpanChange,
  dragControls,
  children
}) => {
  const palette = usePalette();
  return (
    <Surface style={{ padding: SPACE.x16, height: '100%', width: '100%', boxSizing: 'border-box', overflow: 'visible' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          gap: SPACE.x12,
          marginBottom: SPACE.x12
        }}
      >
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {arranging ? (
              <span
                onPointerDown={(event) => dragControls?.start(event)}
                style={{
                  display: 'inline-flex',
                  color: palette.textTertiary,
                  cursor: 'grab',
                  touchAction: 'none'
                }}
                aria-label={`Reorder ${title}`}
              >
                <DragIndicator sx={{ fontSize: 16 }} />
              </span>
            ) : null}
            <Text as="div" variant="h2">
              {title}
            </Text>
          </div>
          {hint ? (
            <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 0' }}>
              {hint}
            </Text>
          ) : null}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
          {arranging ? (
            <Segmented
              value={span}
              onChange={onSpanChange}
              options={[
                { value: 'half', label: 'Half' },
                { value: 'full', label: 'Full' }
              ]}
            />
          ) : (
            actions
          )}
        </div>
      </div>
      {children}
    </Surface>
  );
};

export const ArrangeGrid = ({ order, spans, arranging, onReorder, onSpanChange, childrenById }) => {
  return (
    <>
      <style>{`
        .raptor-dashboard-grid {
          display: grid;
          gap: ${SPACE.x16}px;
          grid-template-columns: 1fr;
          list-style: none;
          margin: 0;
          padding: 0;
        }
        @media (min-width: 960px) {
          .raptor-dashboard-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
      `}</style>
      <Reorder.Group
        as="div"
        axis="xy"
        values={order}
        onReorder={onReorder}
        className="raptor-dashboard-grid"
      >
        {order.map((id) => (
          <ArrangeItem
            key={id}
            id={id}
            span={spans[id] || 'half'}
            arranging={arranging}
            onSpanChange={(next) => onSpanChange(id, next)}
          >
            {childrenById[id]}
          </ArrangeItem>
        ))}
      </Reorder.Group>
    </>
  );
};

const ArrangeItem = ({ id, span, arranging, onSpanChange, children }) => {
  const controls = useDragControls();
  const child = React.isValidElement(children)
    ? React.cloneElement(children, {
        arranging,
        span,
        onSpanChange,
        dragControls: controls
      })
    : children;
  return (
    <Reorder.Item
      as="div"
      value={id}
      dragListener={false}
      dragControls={arranging ? controls : undefined}
      style={{
        gridColumn: span === 'full' ? '1 / -1' : 'auto',
        position: 'relative',
        minWidth: 0,
        overflow: 'visible'
      }}
    >
      {child}
    </Reorder.Item>
  );
};
