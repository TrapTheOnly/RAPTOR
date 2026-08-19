import React from 'react';
import { AccountTree, FileDownload, Security, OpenInNew } from '@mui/icons-material';
import { Bar, Button, Mono, Text } from '../../../design/primitives';
import { ROW, SPACE, TYPE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import { INVENTORY_CELL, INVENTORY_COLGROUP_FLAT, INVENTORY_COLGROUP_GROUPED, RECORDS_HEADERS_FLAT, RECORDS_HEADERS_GROUPED } from '../constants';

export const InventoryHead = ({ grouped }) => {
  const palette = usePalette();
  const headers = grouped ? RECORDS_HEADERS_GROUPED : RECORDS_HEADERS_FLAT;
  const columns = grouped ? INVENTORY_COLGROUP_GROUPED : INVENTORY_COLGROUP_FLAT;
  return (
    <>
      <colgroup>
        {columns.map((width, index) => (
          <col key={headers[index] ? `${headers[index]}-${index}` : `col-${index}`} style={width === 'auto' ? undefined : { width }} />
        ))}
      </colgroup>
      <thead>
        <tr>
          {headers.map((label, index) => (
            <th
              key={`${label}-${index}`}
              style={{
                ...INVENTORY_CELL,
                position: 'sticky',
                top: 0,
                zIndex: 2,
                background: palette.surface,
                borderBottom: `1px solid ${palette.line}`,
                fontWeight: 500
              }}
            >
              <Text as="div" variant="micro" tone="tertiary">
                {label}
              </Text>
            </th>
          ))}
        </tr>
      </thead>
    </>
  );
};

const pad = (value) => (value > 0 ? String(value).padStart(2, '0') : '—');

const AppGroupSection = ({
  group,
  expanded,
  onToggle,
  canViewSecurityDashboard,
  canViewPentestPage,
  canManageApps,
  canExportRecords,
  onOpenApp,
  onOpenPentest,
  onManageApps,
  onExportGroup
}) => {
  const palette = usePalette();
  const prodShare = group.hosts ? Math.round((group.prod / group.hosts) * 100) : 0;
  const appId = group.key.startsWith('app-') ? group.key.slice(4) : null;
  const sourceLine = [
    `${group.hosts} host${group.hosts === 1 ? '' : 's'}`,
    ...group.sources.slice(0, 2),
    group.sources.length > 2 ? `+${group.sources.length - 2}` : null,
    group.manualCount ? `${group.manualCount} manual` : null
  ]
    .filter(Boolean)
    .join(' · ');

  const actions = [];
  if (appId && canViewSecurityDashboard) {
    actions.push(
      <Button key="open" size="small" startIcon={<OpenInNew sx={{ fontSize: 14 }} />} onClick={() => onOpenApp(appId)}>
        Open app
      </Button>
    );
  }
  if (appId && canViewPentestPage && canViewSecurityDashboard) {
    actions.push(
      <Button
        key="pentest"
        size="small"
        variant="outlined"
        startIcon={<Security sx={{ fontSize: 14 }} />}
        onClick={() => onOpenPentest(appId)}
      >
        Pentest
      </Button>
    );
  }
  if (canExportRecords) {
    actions.push(
      <Button key="export" size="small" startIcon={<FileDownload sx={{ fontSize: 14 }} />} onClick={() => onExportGroup(group)}>
        Export hosts
      </Button>
    );
  }
  if (appId && canManageApps) {
    actions.push(
      <Button
        key="manage"
        size="small"
        startIcon={<AccountTree sx={{ fontSize: 14 }} />}
        onClick={onManageApps}
      >
        Manage
      </Button>
    );
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '28px minmax(180px, 1fr) minmax(160px, 220px) auto',
        gridTemplateRows: expanded ? '44px 44px' : '44px',
        alignItems: 'center',
        minHeight: expanded ? ROW.comfortable * 2 : ROW.comfortable,
        background: palette.raised,
        color: palette.text,
        overflow: 'hidden'
      }}
    >
      <button
        type="button"
        onClick={onToggle}
        style={{
          gridColumn: '1 / 2',
          gridRow: '1 / 2',
          height: '100%',
          border: 0,
          background: 'transparent',
          color: palette.textTertiary,
          cursor: 'pointer',
          ...TYPE.micro
        }}
        aria-expanded={expanded}
        aria-label={expanded ? `Collapse ${group.name}` : `Expand ${group.name}`}
      >
        {expanded ? '▾' : '▸'}
      </button>
      <button
        type="button"
        onClick={onToggle}
        style={{
          gridColumn: '2 / 3',
          gridRow: '1 / 2',
          minWidth: 0,
          height: '100%',
          border: 0,
          background: 'transparent',
          color: palette.text,
          cursor: 'pointer',
          textAlign: 'left',
          paddingRight: SPACE.x12
        }}
      >
        <Text as="div" variant="bodyStrong" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {group.name}
        </Text>
        <Text as="div" variant="micro" tone="tertiary" style={{ marginTop: 2 }}>
          {sourceLine}
        </Text>
      </button>
      <div style={{ gridColumn: '3 / 4', gridRow: '1 / 2', paddingRight: SPACE.x12 }}>
        {group.hosts === 0 ? (
          <Text variant="micro" tone="tertiary">
            Empty
          </Text>
        ) : (
          <>
            <Bar value={prodShare} color={palette.accent} />
            <Text as="div" variant="micro" tone="tertiary" style={{ marginTop: 4 }}>
              {group.prod === 0 ? 'No production hosts' : `${group.prod} production · ${group.other} other`}
            </Text>
          </>
        )}
      </div>
      <div
        style={{
          gridColumn: '4 / 5',
          gridRow: '1 / 2',
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 72px)',
          justifyContent: 'end',
          paddingRight: SPACE.x12
        }}
      >
        {[
          { label: 'Miss', value: group.missing, hot: group.missing > 0 },
          { label: 'Cf', value: group.conflicts, hot: group.conflicts > 0 },
          { label: 'Hosts', value: group.hosts, hot: false }
        ].map((slot) => (
          <span key={slot.label}>
            <Text as="div" variant="micro" tone="tertiary">
              {slot.label}
            </Text>
            <Mono
              style={{
                fontSize: 13,
                color: slot.hot ? palette.severity.critical : palette.text
              }}
            >
              {slot.label === 'Hosts' ? group.hosts : pad(slot.value)}
            </Mono>
          </span>
        ))}
      </div>
      {expanded ? (
        <div
          style={{
            gridColumn: '2 / -1',
            gridRow: '2 / 3',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: 8,
            flexWrap: 'wrap',
            paddingRight: SPACE.x12,
            borderTop: `1px solid ${palette.line}`
          }}
        >
          {actions.length ? (
            actions
          ) : (
            <Text variant="meta" tone="tertiary">
              No app actions for this role
            </Text>
          )}
        </div>
      ) : null}
    </div>
  );
};

const AppGroupsList = ({
  groups,
  expandedApps,
  onToggleAppGroup,
  renderRecordCard,
  canViewSecurityDashboard,
  canViewPentestPage,
  canManageApps,
  canExportRecords,
  onOpenApp,
  onOpenPentest,
  onManageApps,
  onExportGroup
}) => {
  const palette = usePalette();
  if (groups.length === 0) return null;

  return groups.map((group) => (
    <tbody key={group.key}>
      <tr>
        <td
          colSpan={RECORDS_HEADERS_GROUPED.length}
          style={{ padding: 0, borderBottom: `1px solid ${palette.line}`, width: '100%', maxWidth: 0 }}
        >
          <AppGroupSection
            group={group}
            expanded={expandedApps.has(group.key)}
            onToggle={() => onToggleAppGroup(group.key)}
            canViewSecurityDashboard={canViewSecurityDashboard}
            canViewPentestPage={canViewPentestPage}
            canManageApps={canManageApps}
            canExportRecords={canExportRecords}
            onOpenApp={onOpenApp}
            onOpenPentest={onOpenPentest}
            onManageApps={onManageApps}
            onExportGroup={onExportGroup}
          />
        </td>
      </tr>
      {expandedApps.has(group.key) ? group.records.map(renderRecordCard) : null}
    </tbody>
  ));
};

export default AppGroupsList;
