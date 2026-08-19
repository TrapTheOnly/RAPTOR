import React from 'react';
import { AccountTree, Add } from '@mui/icons-material';
import { Button, Segmented } from '../../../design/primitives';
import { LAYOUT_ID } from '../../../design/motion';

const RecordsToolbar = ({
  groupByApp,
  onToggleGroupByApp,
  canManageApps,
  canCreateManualRecords,
  onOpenCreateDialog,
  onOpenAppsDialog,
  onExpandAll,
  onCollapseAll,
  grouped
}) => (
  <div style={{ display: 'flex', gap: 12, flexShrink: 0, alignItems: 'flex-end', whiteSpace: 'nowrap' }}>
    <Segmented
      layoutId={LAYOUT_ID.recordsView}
      value={groupByApp}
      onChange={onToggleGroupByApp}
      options={[
        { value: true, label: 'Apps' },
        { value: false, label: 'Flat' }
      ]}
    />
    {grouped ? (
      <>
        <Button size="small" onClick={onExpandAll}>
          Expand all
        </Button>
        <Button size="small" onClick={onCollapseAll}>
          Collapse all
        </Button>
      </>
    ) : null}
    {canCreateManualRecords ? (
      <Button size="small" variant="contained" startIcon={<Add />} onClick={onOpenCreateDialog}>
        Add Manual Domain
      </Button>
    ) : null}
    {canManageApps ? (
      <Button size="small" variant="outlined" startIcon={<AccountTree />} onClick={onOpenAppsDialog}>
        Manage apps
      </Button>
    ) : null}
  </div>
);

export default RecordsToolbar;
