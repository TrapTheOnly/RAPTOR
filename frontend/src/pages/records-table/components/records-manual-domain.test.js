import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CreateManualRecordDialog from './CreateManualRecordDialog';
import RecordCard from './RecordCard';
import RecordsToolbar from './RecordsToolbar';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const theme = createTheme();

const mountWithTheme = (ui) => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
  });
  return {
    container,
    unmount: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  };
};

test('records toolbar shows add manual domain button when allowed', () => {
  const view = mountWithTheme(
    <RecordsToolbar
      groupByApp
      onToggleGroupByApp={() => {}}
      canManageApps={false}
      canCreateManualRecords
      onOpenCreateDialog={() => {}}
      onOpenAppsDialog={() => {}}
      theme={theme}
    />
  );

  expect(view.container.textContent).toContain('Add Manual Domain');
  view.unmount();
});

test('create manual record dialog renders required fields and error', () => {
  const view = mountWithTheme(
    <CreateManualRecordDialog
      open
      form={{
        name: '',
        ip_address: '',
        application_id: '',
        application_owner: '',
        maintainer: '',
        open_ports: '',
        description: ''
      }}
      apps={[]}
      busy={false}
      error="Domain and IP address are required."
      onClose={() => {}}
      onChange={() => {}}
      onSubmit={() => {}}
    />
  );

  expect(document.body.textContent).toContain('Add Manual Domain');
  expect(document.body.textContent).toContain('Domain and IP address are required.');
  view.unmount();
});

test('record card shows manual and conflict badges with resolve action', () => {
  const onResolveSyncConflict = jest.fn();
  const view = mountWithTheme(
    <RecordCard
      record={{
        id: 3,
        name: 'api.example.com',
        ip_address: '10.0.0.1',
        source: 'Other',
        status: 'unchanged',
        origin: 'manual',
        sync_conflict: 1,
        sync_conflict_reason: 'manual_domain_matches_import',
        application_name: '',
        application_owner: '',
        maintainer: '',
        open_ports: '',
        description: '',
        last_modification_date: null
      }}
      isExpanded
      isEditing={false}
      editForm={{}}
      apps={[]}
      canModifyRecords={false}
      canDeleteRecords={false}
      canResolveSyncConflicts
      canViewRecordDetails={false}
      canViewPentestPage={false}
      onToggleExpanded={() => {}}
      onUpdateEditForm={() => {}}
      onStartEditing={() => {}}
      onSave={() => {}}
      onCancelEditing={() => {}}
      onDelete={() => {}}
      onResolveSyncConflict={onResolveSyncConflict}
      onOpenHistory={() => {}}
      onOpenPentest={() => {}}
      theme={theme}
    />
  );

  expect(view.container.textContent).toContain('Manual');
  expect(view.container.textContent).toContain('Sync Conflict');

  const resolveButton = Array.from(view.container.querySelectorAll('button')).find((button) =>
    button.textContent.includes('Resolve Conflict')
  );
  expect(resolveButton).toBeTruthy();
  act(() => {
    resolveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  expect(onResolveSyncConflict).toHaveBeenCalledWith(3);
  view.unmount();
});

test('record card does not render stray zero for automated non-conflict records', () => {
  const view = mountWithTheme(
    <RecordCard
      record={{
        id: 4,
        name: 'auto.example.com',
        ip_address: '10.0.0.2',
        source: 'Other',
        status: 'unchanged',
        origin: 'automated',
        sync_conflict: 0,
        sync_conflict_reason: null,
        application_name: '',
        application_owner: '',
        maintainer: '',
        open_ports: '',
        description: '',
        last_modification_date: null
      }}
      isExpanded={false}
      isEditing={false}
      editForm={{}}
      apps={[]}
      canModifyRecords={false}
      canDeleteRecords={false}
      canResolveSyncConflicts
      canViewRecordDetails={false}
      canViewPentestPage={false}
      onToggleExpanded={() => {}}
      onUpdateEditForm={() => {}}
      onStartEditing={() => {}}
      onSave={() => {}}
      onCancelEditing={() => {}}
      onDelete={() => {}}
      onResolveSyncConflict={() => {}}
      onOpenHistory={() => {}}
      onOpenPentest={() => {}}
      theme={theme}
    />
  );

  expect(view.container.textContent).not.toContain('Resolve Conflict');
  expect(view.container.textContent).not.toContain('Sync Conflict');
  view.unmount();
});
