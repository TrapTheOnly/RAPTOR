import React from 'react';
import { DataList, DataRow, StatusGlyph, Tag, Text } from '../../../design/primitives';
import { RECENT_PAGE_SIZE } from '../constants';
import { formatActivityTimestamp } from '../utils';
import { WidgetCard } from './ArrangeGrid';
import { WidgetPager, usePagedRows } from './WidgetPager';

const TYPE_LABEL = {
  finding_filed: 'Finding',
  test_started: 'Started',
  test_completed: 'Completed',
  scope_updated: 'Scope',
  scope_missing: 'Missing'
};

const RecentActivityWidget = ({
  events = [],
  arranging,
  span,
  onSpanChange,
  dragControls,
  onOpen
}) => {
  const paged = usePagedRows(events, RECENT_PAGE_SIZE);
  return (
    <WidgetCard
      title="Recent activity"
      hint="Findings filed, tests started or completed, and inventory changes."
      arranging={arranging}
      span={span}
      onSpanChange={onSpanChange}
      dragControls={dragControls}
    >
      {events.length === 0 ? (
        <Text variant="meta" tone="secondary">
          No changes in the last 30 days.
        </Text>
      ) : (
        <>
          <DataList>
            {paged.slice.map((event) => (
              <DataRow
                key={event.id}
                id={event.id}
                onToggle={!arranging && onOpen ? () => onOpen(event) : undefined}
                title={<Text variant="bodyStrong">{event.title}</Text>}
                meta={
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                    <Tag>{TYPE_LABEL[event.type] || event.type}</Tag>
                    <Text variant="meta" tone="secondary">
                      {event.subtitle}
                    </Text>
                  </div>
                }
                trailing={
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10 }}>
                    <Text variant="meta" tone="secondary">
                      {formatActivityTimestamp(event.timestamp)}
                    </Text>
                    {event.type === 'finding_filed' ? <StatusGlyph status={event.subtitle} /> : null}
                  </span>
                }
              />
            ))}
          </DataList>
          <WidgetPager
            page={paged.page}
            pageCount={paged.pageCount}
            total={paged.total}
            pageSize={RECENT_PAGE_SIZE}
            onPageChange={paged.setPage}
          />
        </>
      )}
    </WidgetCard>
  );
};

export default RecentActivityWidget;
