import React from 'react';
import { DataList, DataRow, Mono, Tag, Text } from '../../../design/primitives';
import { APPS_PAGE_SIZE } from '../constants';
import { WidgetCard } from './ArrangeGrid';
import { WidgetPager, usePagedRows } from './WidgetPager';

const AppsAtRiskWidget = ({
  apps = [],
  arranging,
  span,
  onSpanChange,
  dragControls,
  onOpen
}) => {
  const paged = usePagedRows(apps, APPS_PAGE_SIZE);
  return (
    <WidgetCard
      title="Apps needing attention"
      hint="Open findings first, then untested in-scope hosts."
      arranging={arranging}
      span={span}
      onSpanChange={onSpanChange}
      dragControls={dragControls}
    >
      {apps.length === 0 ? (
        <Text variant="meta" tone="secondary">
          No open findings or coverage gaps on applications.
        </Text>
      ) : (
        <>
          <DataList>
            {paged.slice.map((app) => (
              <DataRow
                key={app.id}
                id={`app-${app.id}`}
                onToggle={!arranging && onOpen ? () => onOpen(app) : undefined}
                title={<Text variant="bodyStrong">{app.name}</Text>}
                meta={
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                    <Tag>{app.openFindingCount} open</Tag>
                    <Text variant="meta" tone="secondary">
                      {app.startedCount}/{app.inScopeCount} tested
                    </Text>
                  </div>
                }
                trailing={<Mono tone="secondary">{app.openFindingCount}</Mono>}
              />
            ))}
          </DataList>
          <WidgetPager
            page={paged.page}
            pageCount={paged.pageCount}
            total={paged.total}
            pageSize={APPS_PAGE_SIZE}
            onPageChange={paged.setPage}
          />
        </>
      )}
    </WidgetCard>
  );
};

export default AppsAtRiskWidget;
