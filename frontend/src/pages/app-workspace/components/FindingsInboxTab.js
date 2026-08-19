import React, { useMemo, useState } from 'react';
import { InputAdornment, Pagination, Tooltip } from '@mui/material';
import { Add, BugReport, FilterAltOff, Restore, Search, VisibilityOff } from '@mui/icons-material';
import {
  Button,
  Combo,
  DataList,
  EmptyState,
  Field,
  Text,
  Toolbar
} from '../../../design/primitives';
import FindingCard from './FindingCard';
import { usePalette } from '../../../design/usePalette';
import { statusMeta } from '../../../theme/tokens';

const STATUS_OPTIONS = ['', 'open', 'draft', 'retest', 'fixed', 'accepted', 'not_affected'].map((value) => ({
  value,
  label: value ? statusMeta(value).label : 'All statuses'
}));

const SEVERITY_OPTIONS = [
  { value: '0', label: 'Any' },
  { value: '4', label: '4.0+' },
  { value: '7', label: '7.0+' },
  { value: '9', label: '9.0+' }
];

const SORT_OPTIONS = [
  { value: 'severity', label: 'Severity' },
  { value: 'blast', label: 'Blast radius' },
  { value: 'title', label: 'Title' }
];

const FindingsInboxTab = ({
  findings,
  appId,
  total,
  page,
  pageSize,
  onPageChange,
  loading,
  canModify,
  busyFinding,
  statusFilter,
  onStatusFilterChange,
  severityFloor,
  onSeverityFloorChange,
  includeDrafts,
  onIncludeDraftsChange,
  search,
  onSearchChange,
  envScoped,
  onCreateFinding,
  onOccurrenceStatusChange,
  onOpenTicket,
  onOpenMerge,
  onPromote,
  onAttachHosts,
  onBulkRetest
}) => {
  const palette = usePalette();
  const [sort, setSort] = useState('severity');

  const { live, missing } = useMemo(() => {
    const term = search.trim().toLowerCase();
    const matches = (finding) => {
      if (!term) return true;
      const haystack = [
        finding.title,
        finding.categoryName,
        finding.description,
        ...(finding.occurrences || []).map((item) => item.dns_name)
      ]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return haystack.includes(term);
    };

    const sorted = [...findings].filter(matches).sort((a, b) => {
      if (sort === 'blast') return (b.occurrences || []).length - (a.occurrences || []).length;
      if (sort === 'title') return String(a.title || '').localeCompare(String(b.title || ''));
      return Number(b.baseScore || 0) - Number(a.baseScore || 0);
    });

    const isAllMissing = (finding) =>
      (finding.occurrences || []).length > 0 &&
      (finding.occurrences || []).every((occ) => occ.host_status === 'missing');

    return {
      live: sorted.filter((finding) => !isAllMissing(finding)),
      missing: sorted.filter(isAllMissing)
    };
  }, [findings, search, sort]);

  const pageCount = Math.max(1, Math.ceil((total || 0) / pageSize));
  const hasFilters = Boolean(statusFilter || search.trim() || Number(severityFloor) > 0 || !includeDrafts);

  const clearFilters = () => {
    onStatusFilterChange('');
    onSearchChange('');
    onSeverityFloorChange('0');
    onIncludeDraftsChange(true);
  };

  return (
    <div>
      <Toolbar
        nowrap
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(140px, 1fr) 160px 140px 160px 160px 76px max-content',
          alignItems: 'end',
          overflowX: 'auto'
        }}
      >
        <Field
          label="Search"
          placeholder="Findings, narratives, or hosts"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          style={{ width: '100%', minWidth: 0 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search sx={{ fontSize: 16 }} />
              </InputAdornment>
            )
          }}
        />
        <Combo
          label="Status"
          options={STATUS_OPTIONS}
          value={statusFilter}
          onChange={onStatusFilterChange}
          style={{ width: '100%' }}
        />
        <Combo
          label="Min severity"
          options={SEVERITY_OPTIONS}
          value={severityFloor}
          onChange={onSeverityFloorChange}
          style={{ width: '100%' }}
        />
        <Combo
          label="Sort"
          options={SORT_OPTIONS}
          value={sort}
          onChange={setSort}
          style={{ width: '100%' }}
        />
        <Button
          size="small"
          variant="outlined"
          startIcon={<VisibilityOff />}
          onClick={() => onIncludeDraftsChange(!includeDrafts)}
          aria-pressed={!includeDrafts}
          style={{
            width: '100%',
            whiteSpace: 'nowrap',
            ...(includeDrafts
              ? null
              : {
                  backgroundColor: palette.accentFill,
                  color: palette.accent,
                  borderColor: palette.accent
                })
          }}
        >
          {includeDrafts ? 'Hide drafts' : 'Drafts hidden'}
        </Button>
        <Button
          size="small"
          startIcon={<FilterAltOff />}
          onClick={clearFilters}
          disabled={!hasFilters}
          tabIndex={hasFilters ? 0 : -1}
          aria-hidden={!hasFilters}
          style={{ width: '100%', visibility: hasFilters ? 'visible' : 'hidden' }}
        >
          Clear
        </Button>
        <div style={{ display: 'flex', gap: 12, flexShrink: 0, alignItems: 'flex-end', whiteSpace: 'nowrap' }}>
          {canModify && onBulkRetest ? (
            <Tooltip title="Move every open occurrence in this view to retest, ready for a retest pack">
              <Button size="small" variant="outlined" startIcon={<Restore />} onClick={onBulkRetest}>
                Queue retest
              </Button>
            </Tooltip>
          ) : null}
          {canModify ? (
            <Button size="small" variant="contained" startIcon={<Add />} onClick={onCreateFinding}>
              New finding
            </Button>
          ) : null}
        </div>
      </Toolbar>

      {live.length === 0 && missing.length === 0 ? (
        <EmptyState
          icon={BugReport}
          title={hasFilters ? 'No findings match these filters' : 'No findings in this view'}
          hint={
            hasFilters
              ? 'Try widening the severity floor or clearing the search term.'
              : envScoped
                ? 'This environment has no findings yet. Write the finding once at app level and attach the hosts it affects.'
                : 'Write a finding once, then attach every host it affects as an occurrence.'
          }
          actions={
            hasFilters ? (
              <Button variant="outlined" onClick={clearFilters}>
                Clear filters
              </Button>
            ) : canModify ? (
              <Button variant="contained" startIcon={<Add />} onClick={onCreateFinding}>
                New finding
              </Button>
            ) : null
          }
        />
      ) : (
        <DataList>
          {live.map((finding) => (
            <FindingCard
              key={finding.id}
              finding={finding}
              canModify={canModify}
              busy={busyFinding === finding.id}
              onOccurrenceStatusChange={onOccurrenceStatusChange}
              onOpenTicket={onOpenTicket}
              onOpenMerge={onOpenMerge}
              onPromote={onPromote}
              onAttachHosts={onAttachHosts}
            />
          ))}
        </DataList>
      )}

      {missing.length > 0 ? (
        <div style={{ marginTop: 24 }}>
          <Text as="div" variant="h2">
            Findings on missing hosts ({missing.length})
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: '6px 0 12px' }}>
            Every host for these findings has dropped out of DNS inventory. They are kept for history and are
            excluded from packs.
          </Text>
          <DataList>
            {missing.map((finding) => (
              <FindingCard
                key={finding.id}
                appId={appId}
                finding={finding}
                canModify={false}
                busy={false}
                onOccurrenceStatusChange={() => {}}
                onOpenTicket={() => {}}
                onOpenMerge={() => {}}
                onPromote={() => {}}
              />
            ))}
          </DataList>
        </div>
      ) : null}

      {pageCount > 1 ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 16 }}>
          <Pagination count={pageCount} page={page} onChange={(_event, value) => onPageChange(value)} disabled={loading} />
        </div>
      ) : null}
    </div>
  );
};

export default FindingsInboxTab;
