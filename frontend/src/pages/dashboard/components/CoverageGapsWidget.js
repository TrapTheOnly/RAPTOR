import React, { useMemo } from 'react';
import { DataList, DataRow, Tag, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { COVERAGE_PAGE_SIZE } from '../constants';
import { formatRelativeAge } from '../utils';
import { WidgetCard } from './ArrangeGrid';
import { WidgetPager, usePagedRows } from './WidgetPager';

const CoverageGapsWidget = ({
  coverageGaps,
  arranging,
  span,
  onSpanChange,
  dragControls,
  onOpen
}) => {
  const rows = useMemo(() => {
    const neverTested = coverageGaps?.neverTested || [];
    const stale = coverageGaps?.stale || [];
    return [
      ...neverTested.map((item) => ({ ...item, kind: 'never' })),
      ...stale.map((item) => ({ ...item, kind: 'stale' }))
    ];
  }, [coverageGaps]);
  const paged = usePagedRows(rows, COVERAGE_PAGE_SIZE);

  return (
    <WidgetCard
      title="Coverage gaps"
      hint="Never started, then completed tests older than 90 days."
      arranging={arranging}
      span={span}
      onSpanChange={onSpanChange}
      dragControls={dragControls}
    >
      {rows.length === 0 ? (
        <Text variant="meta" tone="secondary">
          Every tracked host has a recent completed test.
        </Text>
      ) : (
        <>
          <DataList>
            {paged.slice.map((item) => (
              <DataRow
                key={`${item.kind}-${item.id}`}
                id={`${item.kind}-${item.id}`}
                onToggle={!arranging && onOpen ? () => onOpen(item) : undefined}
                title={<Text variant="bodyStrong">{item.name}</Text>}
                meta={
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                    <Tag>{item.kind === 'never' ? 'Never tested' : 'Stale'}</Tag>
                    {item.kind === 'stale' ? (
                      <Text variant="meta" tone="secondary">
                        Last {formatRelativeAge(item.lastTested)}
                      </Text>
                    ) : (
                      <Text variant="meta" tone="secondary">
                        {item.source}
                      </Text>
                    )}
                  </div>
                }
              />
            ))}
          </DataList>
          <WidgetPager
            page={paged.page}
            pageCount={paged.pageCount}
            total={paged.total}
            pageSize={COVERAGE_PAGE_SIZE}
            onPageChange={paged.setPage}
          />
          <Text variant="meta" tone="secondary" style={{ marginTop: SPACE.x8 }}>
            {coverageGaps.neverTestedTotal} never tested · {coverageGaps.staleTotal} stale
          </Text>
        </>
      )}
    </WidgetCard>
  );
};

export default CoverageGapsWidget;
