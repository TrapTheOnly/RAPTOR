import React from 'react';
import { DataList, DataRow, Mono, Tag, Text } from '../../../design/primitives';
import { WORKLOAD_PAGE_SIZE } from '../constants';
import { WidgetCard } from './ArrangeGrid';
import { WidgetPager, usePagedRows } from './WidgetPager';

const TesterWorkloadWidget = ({
  rows = [],
  arranging,
  span,
  onSpanChange,
  dragControls
}) => {
  const paged = usePagedRows(rows, WORKLOAD_PAGE_SIZE);
  return (
    <WidgetCard
      title="Tester workload"
      hint="Assigned testers by open findings, then in-progress tests."
      arranging={arranging}
      span={span}
      onSpanChange={onSpanChange}
      dragControls={dragControls}
    >
      {rows.length === 0 ? (
        <Text variant="meta" tone="secondary">
          No assigned tester load yet.
        </Text>
      ) : (
        <>
          <DataList>
            {paged.slice.map((row) => (
              <DataRow
                key={row.tester}
                id={`tester-${row.tester}`}
                title={<Text variant="bodyStrong">{row.tester}</Text>}
                meta={
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                    <Tag>{row.inProgress} in progress</Tag>
                    <Tag>{row.openFindings} open findings</Tag>
                  </div>
                }
                trailing={<Mono tone="secondary">{row.total}</Mono>}
              />
            ))}
          </DataList>
          <WidgetPager
            page={paged.page}
            pageCount={paged.pageCount}
            total={paged.total}
            pageSize={WORKLOAD_PAGE_SIZE}
            onPageChange={paged.setPage}
          />
        </>
      )}
    </WidgetCard>
  );
};

export default TesterWorkloadWidget;
