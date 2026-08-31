import { hostNotebookPath, routeShellKey } from './navigation';

const readSource = (relativePath) =>
  require('fs').readFileSync(require('path').join(__dirname, relativePath), 'utf8');

test('routeShellKey keeps app and env drill-down on one surface', () => {
  expect(routeShellKey('/apps/12')).toBe('apps/12');
  expect(routeShellKey('/apps/12/envs/4')).toBe('apps/12');
  expect(routeShellKey('/apps/12/envs/4/')).toBe('apps/12');
  expect(routeShellKey('/apps/12/waves/3/scan-live')).toBe('apps/12/scan-live');
  expect(routeShellKey('/apps/12/findings/abc')).toBe('apps/12');
});

test('routeShellKey treats docs as one surface and leaves other products distinct', () => {
  expect(routeShellKey('/docs')).toBe('docs');
  expect(routeShellKey('/docs/admin/overview')).toBe('docs');
  expect(routeShellKey('/pentest')).toBe('/pentest');
  expect(routeShellKey('/pentest/record/9')).toBe('pentest/record/9');
  expect(routeShellKey('/records')).toBe('/records');
  expect(routeShellKey('/records/record/9')).toBe('records/9');
});

test('host notebooks require a wave id', () => {
  expect(hostNotebookPath(9, 3)).toBe('/pentest/record/9?wave=3');
  expect(hostNotebookPath(9, null)).toBe(null);
  expect(hostNotebookPath(9, '')).toBe(null);
});

test('buttons default to outlined and refresh uses the shared control', () => {
  const theme = readSource('./theme.js');
  const chrome = readSource('./primitives/chrome.js');
  expect(theme).toContain("defaultProps: { disableElevation: true, disableRipple: true, variant: 'outlined' }");
  expect(chrome).toContain('export const RefreshButton');
  expect(readSource('../pages/RecordsTable.js')).toContain('RefreshButton');
  expect(readSource('../pages/PentestDashboard.js')).toContain('RefreshButton');
  expect(readSource('../pages/Dashboard.js')).toContain('RefreshButton');
});

test('command palette filters nav by permission and jumps to waves, not host notebooks', () => {
  const palette = readSource('./primitives/CommandPalette.js');
  const header = readSource('../components/ModernHeader.js');
  expect(palette).toContain('userRole');
  expect(palette).toContain('userPermissions');
  expect(palette).toContain('hasPermission');
  expect(palette).toContain("permission: 'view_dashboard'");
  expect(palette).toContain("permission: 'view_records'");
  expect(palette).toContain("permission: 'view_security_dashboard'");
  expect(palette).toContain("permission: 'view_settings'");
  expect(palette).toContain("to: '/docs'");
  expect(palette).not.toMatch(/nav-docs[\s\S]{0,80}permission:/);
  expect(palette).toContain('view_pentest_page');
  expect(palette).toContain("to: `/apps/${wave.appId}/waves/${wave.id}`");
  expect(palette).toContain("to: `/apps/${finding.appId}/findings/${finding.id}`");
  expect(palette).toContain('Jump to an app, wave, or finding');
  expect(palette).not.toContain('/api/hosts/search');
  expect(palette).not.toContain("to: `/pentest/record/${host.id}`");
  expect(header).toContain('userRole={userRole}');
  expect(header).toContain('userPermissions={userPermissions}');
  expect(header).toContain('RaptorMark');
  expect(header).toContain('variant="mark"');
  expect(header).toContain('variant="wordmark"');
});
