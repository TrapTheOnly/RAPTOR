import React from 'react';
import { InputAdornment } from '@mui/material';
import { FilterAltOff, Search } from '@mui/icons-material';
import {
  Button,
  Combo,
  Field,
  Surface,
  Tag,
  Text,
  Toolbar
} from '../../../design/primitives';
import { ORIGIN_FILTER_OPTIONS, STATUS_FILTER_OPTIONS } from '../constants';
import { usePalette } from '../../../design/usePalette';
import RecordsToolbar from './RecordsToolbar';

const SearchFiltersSection = ({
  activeFilters,
  searchQuery,
  searchInput,
  dropdownOpen,
  suggestions,
  onClearAllFilters,
  onRemoveFilter,
  onSetSearchQuery,
  onSetSearchInput,
  onInputChange,
  onSubmitSearch,
  onSelectSuggestion,
  onSetDropdownOpen,
  statusFilter,
  onStatusFilterChange,
  originFilter,
  onOriginFilterChange,
  sourceFilter,
  onSourceFilterChange,
  appFilter,
  onAppFilterChange,
  conflictFilter,
  sourceOptions,
  appOptions,
  groupByApp,
  onToggleGroupByApp,
  canManageApps,
  canCreateManualRecords,
  onOpenCreateDialog,
  onOpenAppsDialog,
  onExpandAll,
  onCollapseAll
}) => {
  const palette = usePalette();
  const hasFilters = Boolean(
    activeFilters.length ||
      searchQuery ||
      statusFilter ||
      originFilter ||
      sourceFilter ||
      appFilter ||
      conflictFilter
  );

  return (
    <div>
      <Toolbar
        nowrap
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          overflowX: 'auto'
        }}
      >
        <RecordsToolbar
          groupByApp={groupByApp}
          onToggleGroupByApp={onToggleGroupByApp}
          canManageApps={canManageApps}
          canCreateManualRecords={canCreateManualRecords}
          onOpenCreateDialog={onOpenCreateDialog}
          onOpenAppsDialog={onOpenAppsDialog}
          onExpandAll={onExpandAll}
          onCollapseAll={onCollapseAll}
          grouped={groupByApp}
        />
      </Toolbar>

      <Toolbar
        nowrap
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(240px, 1fr) 140px 140px 160px 180px 76px',
          alignItems: 'end',
          overflowX: 'auto',
          marginBottom: 12
        }}
      >
        <div style={{ position: 'relative', minWidth: 0 }}>
          <Field
            label="Search"
            placeholder="Hostname, IP, or field=value"
            value={searchInput}
            onChange={(event) => onInputChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                if (dropdownOpen && suggestions.length > 0) {
                  onSelectSuggestion(suggestions[0]);
                } else {
                  onSubmitSearch();
                }
              } else if (event.key === 'Tab' && dropdownOpen && suggestions.length > 0) {
                event.preventDefault();
                onSelectSuggestion(suggestions[0]);
              } else if (event.key === 'Escape') {
                onSetDropdownOpen(false);
              }
            }}
            style={{ width: '100%', minWidth: 0 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search sx={{ fontSize: 16 }} />
                </InputAdornment>
              )
            }}
          />
          {dropdownOpen && suggestions.length > 0 ? (
            <Surface
              raised
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                zIndex: 20,
                marginTop: 4,
                maxHeight: 280,
                overflow: 'auto'
              }}
            >
              {suggestions.map((suggestion, index) => (
                <button
                  key={`${suggestion.type}-${suggestion.display}-${index}`}
                  type="button"
                  onClick={() => onSelectSuggestion(suggestion)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    width: '100%',
                    textAlign: 'left',
                    background: 'transparent',
                    border: 0,
                    borderBottom: index < suggestions.length - 1 ? `1px solid ${palette.line}` : 0,
                    padding: '8px 12px',
                    cursor: 'pointer',
                    color: palette.text
                  }}
                >
                  <span style={{ minWidth: 0 }}>
                    <Text as="div" variant="bodyStrong">
                      {suggestion.display}
                    </Text>
                    {suggestion.description ? (
                      <Text as="div" variant="meta" tone="secondary">
                        {suggestion.description}
                      </Text>
                    ) : null}
                  </span>
                  {suggestion.count !== undefined ? <Tag>{suggestion.count}</Tag> : null}
                </button>
              ))}
            </Surface>
          ) : null}
        </div>
        <Combo
          label="Status"
          options={STATUS_FILTER_OPTIONS}
          value={statusFilter}
          onChange={onStatusFilterChange}
          style={{ width: '100%' }}
        />
        <Combo
          label="Origin"
          options={ORIGIN_FILTER_OPTIONS}
          value={originFilter}
          onChange={onOriginFilterChange}
          style={{ width: '100%' }}
        />
        <Combo
          label="Source"
          options={sourceOptions}
          value={sourceFilter}
          onChange={onSourceFilterChange}
          style={{ width: '100%' }}
        />
        <Combo
          label="Application"
          options={appOptions}
          value={appFilter}
          onChange={onAppFilterChange}
          style={{ width: '100%' }}
        />
        <Button
          size="small"
          startIcon={<FilterAltOff />}
          onClick={onClearAllFilters}
          disabled={!hasFilters}
          tabIndex={hasFilters ? 0 : -1}
          aria-hidden={!hasFilters}
          style={{ width: '100%', visibility: hasFilters ? 'visible' : 'hidden' }}
        >
          Clear
        </Button>
      </Toolbar>

      {activeFilters.length > 0 || searchQuery ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
          {activeFilters.map((filter) => (
            <button
              key={filter.id}
              type="button"
              onClick={() => onRemoveFilter(filter.id)}
              style={{ background: 'transparent', border: 0, padding: 0, cursor: 'pointer' }}
              aria-label={`Remove filter ${filter.label}`}
            >
              <Tag emphasized={filter.hasWildcards}>{filter.label} ×</Tag>
            </button>
          ))}
          {searchQuery ? (
            <button
              type="button"
              onClick={() => {
                onSetSearchQuery('');
                onSetSearchInput('');
              }}
              style={{ background: 'transparent', border: 0, padding: 0, cursor: 'pointer' }}
              aria-label="Clear search text"
            >
              <Tag>{`Search: ${searchQuery} ×`}</Tag>
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
};

export default SearchFiltersSection;
