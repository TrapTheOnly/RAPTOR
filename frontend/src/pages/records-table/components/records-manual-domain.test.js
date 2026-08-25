import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import AppGroupsList from './AppGroupsList';
import CreateManualRecordDialog from './CreateManualRecordDialog';
import RecordCard from './RecordCard';
import RecordsToolbar from './RecordsToolbar';
import { buildAppGroups, calculateRecordStats, collectUnseenGroupKeys, historyFieldDiffs } from '../utils';

jest.mock(
  'react-router-dom',
  () => ({
    Link: ({ children, ...rest }) => <a {...rest}>{children}</a>,
    useNavigate: () => () => {},
    useParams: () => ({}),
    useSearchParams: () => [new URLSearchParams(), () => {}]
  }),
  { virtual: true }
);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const theme = createTheme();

const readSource = (relativePath) =>
  require('fs').readFileSync(require('path').join(__dirname, relativePath), 'utf8');

const mountedViews = [];

const mountWithTheme = (ui) => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
  });
  let alive = true;
  const view = {
    container,
    unmount: () => {
      if (!alive) return;
      alive = false;
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  };
  mountedViews.push(view);
  return view;
};

const mountCard = (ui) =>
  mountWithTheme(
    <table>
      <tbody>{ui}</tbody>
    </table>
  );

afterEach(() => {
  while (mountedViews.length) {
    mountedViews.pop().unmount();
  }
});

const cardHandlers = {
  isExpanded: false,
  isEditing: false,
  editForm: {},
  apps: [],
  canModifyRecords: false,
  canDeleteRecords: false,
  canResolveSyncConflicts: false,
  canViewRecordDetails: false,
  onToggleExpanded: () => {},
  onUpdateEditForm: () => {},
  onStartEditing: () => {},
  onSave: () => {},
  onCancelEditing: () => {},
  onDelete: () => {},
  onResolveSyncConflict: () => {},
  onOpenHistory: () => {}
};

test('records toolbar shows add manual domain button when allowed', () => {
  const view = mountWithTheme(
    <RecordsToolbar
      groupByApp
      grouped
      onToggleGroupByApp={() => {}}
      canManageApps
      canCreateManualRecords
      onOpenCreateDialog={() => {}}
      onOpenAppsDialog={() => {}}
      onExpandAll={() => {}}
      onCollapseAll={() => {}}
    />
  );

  expect(view.container.textContent).toContain('Add Manual Domain');
  expect(view.container.textContent).toContain('Manage apps');
  expect(view.container.textContent).toContain('Apps');
  expect(view.container.textContent).toContain('Flat');
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
        environment_id: '',
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
  const view = mountCard(
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
      onToggleExpanded={() => {}}
      onUpdateEditForm={() => {}}
      onStartEditing={() => {}}
      onSave={() => {}}
      onCancelEditing={() => {}}
      onDelete={() => {}}
      onResolveSyncConflict={onResolveSyncConflict}
      onOpenHistory={() => {}}
    />
  );

  expect(view.container.textContent).toContain('Manual');
  expect(view.container.textContent).toContain('Conflict');
  expect(view.container.textContent).not.toContain('Pentest');

  const resolveButton = Array.from(view.container.querySelectorAll('button')).find((button) =>
    button.textContent.includes('Resolve conflict')
  );
  expect(resolveButton).toBeTruthy();
  act(() => {
    resolveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  expect(onResolveSyncConflict).toHaveBeenCalledWith(3);
  view.unmount();
});

test('record card does not render stray zero for automated non-conflict records', () => {
  const view = mountCard(
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
      {...cardHandlers}
      canResolveSyncConflicts
    />
  );

  expect(view.container.textContent).not.toContain('Resolve conflict');
  expect(view.container.textContent).not.toContain('Conflict');
  expect(view.container.textContent).not.toContain('Pentest');
  view.unmount();
});

test('expanded groups mount host rows and collapsed groups do not', () => {
  const groups = buildAppGroups([
    {
      id: 1,
      name: 'alpha.example.com',
      application_id: 9,
      application_name: 'Alpha',
      status: 'unchanged',
      origin: 'automated',
      source: 'Corp',
      environment_slug: 'prod'
    },
    {
      id: 2,
      name: 'beta.example.com',
      application_id: null,
      application_name: '',
      status: 'missing',
      origin: 'automated',
      source: 'Corp',
      environment_slug: 'dev'
    }
  ]);
  const view = mountWithTheme(
    <table>
      <AppGroupsList
        groups={groups}
        expandedApps={new Set(groups.map((group) => group.key))}
        onToggleAppGroup={() => {}}
        renderRecordCard={(record) => <RecordCard key={record.id} record={record} {...cardHandlers} grouped />}
        canViewSecurityDashboard
        canViewPentestPage
        canManageApps
        canExportRecords
        onOpenApp={() => {}}
        onOpenPentest={() => {}}
        onManageApps={() => {}}
        onExportGroup={() => {}}
      />
    </table>
  );

  expect(view.container.textContent).toContain('alpha.example.com');
  expect(view.container.textContent).toContain('beta.example.com');
  expect(view.container.textContent).toContain('Pentest');
  expect(view.container.textContent).toContain('Open app');
  view.unmount();

  const collapsed = mountWithTheme(
    <table>
      <AppGroupsList
        groups={groups}
        expandedApps={new Set()}
        onToggleAppGroup={() => {}}
        renderRecordCard={(record) => <RecordCard key={record.id} record={record} {...cardHandlers} grouped />}
      />
    </table>
  );
  expect(collapsed.container.textContent).not.toContain('alpha.example.com');
  expect(collapsed.container.textContent).toContain('Alpha');
  expect(collapsed.container.textContent).not.toContain('Pentest');
  collapsed.unmount();
});

test('host counts on groups match the filtered set', () => {
  const records = [
    { id: 1, application_id: 1, application_name: 'A', status: 'unchanged', sync_conflict: 0, environment_slug: 'prod' },
    { id: 2, application_id: 1, application_name: 'A', status: 'missing', sync_conflict: 0, environment_slug: 'dev' },
    { id: 3, application_id: null, application_name: '', status: 'updated', sync_conflict: 1, environment_slug: 'prod' }
  ];
  const groups = buildAppGroups(records);
  const stats = calculateRecordStats(records);
  expect(groups.reduce((sum, group) => sum + group.hosts, 0)).toBe(records.length);
  expect(stats.total).toBe(records.length);
  expect(stats.missing).toBe(1);
  expect(stats.conflicts).toBe(1);
  expect(stats.prod).toBe(2);
});

test('new group keys expand on first sight without reopening collapsed ones', () => {
  const seen = new Set();
  const first = collectUnseenGroupKeys(seen, ['app-1', 'app-2']);
  first.forEach((key) => seen.add(key));
  expect(first).toEqual(['app-1', 'app-2']);
  expect(collectUnseenGroupKeys(seen, ['app-1', 'app-2', 'app-3'])).toEqual(['app-3']);
});

test('history diffs list only fields that changed', () => {
  const diffs = historyFieldDiffs({
    old_ip_address: null,
    new_ip_address: '10.20.19.21',
    old_source: null,
    new_source: 'Other',
    old_maintainer: 'tom.becker',
    new_maintainer: 'tom.becker'
  });
  expect(diffs.map((field) => field.label)).toEqual(['IP', 'Source']);
});

test('records inventory uses Operator Console primitives', () => {
  const files = [
    '../../RecordsTable.js',
    '../../Record.js',
    './AppGroupsList.js',
    './CreateManualRecordDialog.js',
    './ManageAppsDialog.js',
    './RecordCard.js',
    './RecordsStatsBar.js',
    './RecordsToolbar.js',
    './SearchFiltersSection.js'
  ];
  files.forEach((file) => {
    const source = readSource(file);
    expect(source).not.toContain('<Select');
    expect(source).not.toContain('<Autocomplete');
    expect(source).not.toContain('<TextField');
    expect(source).not.toContain('<InputLabel');
    expect(source).not.toContain('SectionCard');
    expect(source).not.toContain('<Dialog');
    expect(source).not.toContain('<Card');
  });
  const page = readSource('../../RecordsTable.js');
  expect(page).toContain("from '../design/primitives'");
  expect(page).toContain("from '../components/program/PageHeader'");
  expect(page).toContain("from '../utils/permissions'");
  expect(page).toContain('hasRolePermission');
  expect(page).toContain("normalizedRole === 'admin' || normalizedRole === 'manager'");
  expect(page).toContain('<Progress deferred');
  expect(page).toContain('Asset Inventory');
  expect(page).toContain('INVENTORY_TABLE');
  expect(page).not.toContain('hosts ·');
  expect(readSource('../constants.js')).toContain("tableLayout: 'fixed'");
  expect(page).toContain('InventoryHead');
  expect(page).toContain('calculateRecordStats(searchFiltered)');
  expect(page).not.toContain('calculateRecordStats(filteredRecords)');
  expect(page).not.toContain('MetricStrip');
  expect(page).not.toContain('/pentest/record/');
  expect(page).not.toContain('if (loading)');
  expect(page).not.toContain('window.confirm');
  const toolbar = readSource('./RecordsToolbar.js');
  expect(toolbar).toContain('Segmented');
  expect(toolbar).toContain('Add Manual Domain');
  expect(toolbar).toContain('Manage apps');
  const filters = readSource('./SearchFiltersSection.js');
  expect(filters).toContain('gridTemplateColumns');
  expect(filters).toContain("visibility: hasFilters ? 'visible' : 'hidden'");
  expect(filters).toContain('<RecordsToolbar');
  expect(filters).not.toContain('Conflict ×');
  const statsBar = readSource('./RecordsStatsBar.js');
  expect(statsBar).toContain('inventoryCount');
  expect(statsBar).not.toContain("label: 'Prod'");
  const card = readSource('./RecordCard.js');
  expect(card).not.toContain('Pentest');
  expect(card).toContain('Open asset');
  const groups = readSource('./AppGroupsList.js');
  expect(groups).toContain('Pentest');
  expect(groups).toContain('ROW.comfortable * 2');
  const asset = readSource('../../Record.js');
  expect(asset).toContain("from '../design/primitives'");
  expect(asset).not.toContain('<Card');
  expect(asset).not.toContain('<Dialog');
  expect(asset).not.toContain('<Select');
  expect(asset).not.toContain('<TextField');
});
