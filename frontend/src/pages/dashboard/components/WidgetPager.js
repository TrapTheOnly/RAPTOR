import React, { useEffect, useState } from 'react';
import { Button, Mono, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';

export const usePagedRows = (rows = [], pageSize) => {
  const [page, setPage] = useState(1);
  const total = Array.isArray(rows) ? rows.length : 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize) || 1);

  useEffect(() => {
    setPage((current) => Math.min(current, pageCount));
  }, [pageCount]);

  const start = (page - 1) * pageSize;
  return {
    page,
    setPage,
    pageCount,
    total,
    slice: (rows || []).slice(start, start + pageSize)
  };
};

export const WidgetPager = ({ page, pageCount, total, pageSize, onPageChange }) => {
  if (total <= pageSize) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        gap: SPACE.x12,
        marginTop: SPACE.x12
      }}
    >
      <Text variant="meta" tone="secondary">
        {start}–{end} of {total}
      </Text>
      <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8 }}>
        <Button size="small" variant="outlined" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Prev
        </Button>
        <Mono tone="secondary">
          {page}/{pageCount}
        </Mono>
        <Button
          size="small"
          variant="outlined"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          Next
        </Button>
      </div>
    </div>
  );
};
