import { routeShellKey } from './navigation';

test('routeShellKey keeps app and env drill-down on one surface', () => {
  expect(routeShellKey('/apps/12')).toBe('apps/12');
  expect(routeShellKey('/apps/12/envs/4')).toBe('apps/12');
  expect(routeShellKey('/apps/12/envs/4/')).toBe('apps/12');
});

test('routeShellKey treats docs as one surface and leaves other products distinct', () => {
  expect(routeShellKey('/docs')).toBe('docs');
  expect(routeShellKey('/docs/admin/overview')).toBe('docs');
  expect(routeShellKey('/pentest')).toBe('/pentest');
  expect(routeShellKey('/pentest/record/9')).toBe('pentest/record/9');
  expect(routeShellKey('/records')).toBe('/records');
  expect(routeShellKey('/records/record/9')).toBe('records/9');
});
