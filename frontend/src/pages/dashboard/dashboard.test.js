import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import { LineChart } from '../../design/primitives';
import createRaptorTheme from '../../design/theme';
import { buildDashboardViewModel, buildKpis } from './utils';
import { sliceWeekly } from './layout';

jest.mock(
  'react-router-dom',
  () => ({
    Link: ({ children, ...rest }) => <a {...rest}>{children}</a>,
    useNavigate: () => () => {}
  }),
  { virtual: true }
);

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const theme = createRaptorTheme(true);
const fs = require('fs');
const path = require('path');

const readSource = (relativePath) => fs.readFileSync(path.join(__dirname, relativePath), 'utf8');

const mountedViews = [];
const mount = (ui) => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
  });
  const view = {
    container,
    unmount: () => {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  };
  mountedViews.push(view);
  return view;
};

afterEach(() => {
  while (mountedViews.length) {
    mountedViews.pop().unmount();
  }
});

test('kpis prefer live findings over pentest-record flags', () => {
  const now = new Date('2026-08-20T12:00:00Z');
  const kpis = buildKpis(
    {
      pentestRecords: [
        { recordId: 1, status: 'Not Started', tested_by: '', test_end_date: null },
        {
          recordId: 2,
          status: 'Completed',
          tested_by: 'ada',
          test_end_date: '2026-01-01',
          vulnerability_fixed: 1,
          finding_count: 4
        },
        { recordId: 3, status: 'In Progress', tested_by: 'ada' }
      ],
      findingsSummary: {
        open: 3,
        closed: 1,
        bySeverity: { critical: 1, high: 1, medium: 1, low: 0, none: 0 },
        weekly: [
          { opened: 2, closed: 0 },
          { opened: 1, closed: 4 },
          { opened: 0, closed: 0 },
          { opened: 0, closed: 0 },
          { opened: 1, closed: 1 }
        ]
      }
    },
    now
  );

  expect(kpis.openFindings).toBe(3);
  expect(kpis.criticalHigh).toBe(2);
  expect(kpis.neverTested).toBe(1);
  expect(kpis.stale).toBe(1);
  expect(kpis.unassigned).toBe(1);
  expect(kpis.openedLast30d).toBe(4);
  expect(kpis.closedLast30d).toBe(5);
});

test('view model drops empty-risk apps and omits unassigned testers', () => {
  const view = buildDashboardViewModel(
    {
      records: [],
      pentestRecords: [
        { recordId: 1, name: 'a.example', status: 'In Progress', tested_by: '', finding_count: 2 },
        { recordId: 2, name: 'b.example', status: 'In Progress', tested_by: 'ada', finding_count: 9 }
      ],
      findingsSummary: {
        open: 2,
        closed: 0,
        bySeverity: { critical: 0, high: 2, medium: 0, low: 0, none: 0 },
        weekly: [],
        recent: []
      },
      applications: [
        { id: 1, name: 'Quiet', open_finding_count: 0, in_scope_count: 2, started_count: 2 },
        { id: 2, name: 'Loud', open_finding_count: 4, in_scope_count: 3, started_count: 1 }
      ]
    },
    new Date('2026-08-20T12:00:00Z')
  );

  expect(view.appsAtRisk.map((app) => app.name)).toEqual(['Loud']);
  expect(view.testerWorkload.map((row) => row.tester)).toEqual(['ada']);
});

test('sliceWeekly keeps the trailing window', () => {
  const weekly = Array.from({ length: 26 }, (_, index) => ({ label: String(index) }));
  expect(sliceWeekly(weekly, '4w')).toHaveLength(4);
  expect(sliceWeekly(weekly, '12w')[0].label).toBe('14');
  expect(sliceWeekly(weekly, '6m')).toHaveLength(26);
});

test('line chart hover tooltip prints series values', () => {
  const view = mount(
    <LineChart
      series={[
        { key: 'opened', label: 'Opened', color: '#ff0', points: [1, 4, 2], labels: ['Aug 4', 'Aug 11', 'Aug 18'] },
        { key: 'closed', label: 'Closed', color: '#0f0', points: [0, 1, 3], labels: ['Aug 4', 'Aug 11', 'Aug 18'] }
      ]}
    />
  );
  const svg = view.container.querySelector('svg');
  expect(svg).toBeTruthy();
  svg.getBoundingClientRect = () => ({ width: 520, height: 180, left: 0, top: 0, right: 520, bottom: 180 });
  act(() => {
    svg.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 400, clientY: 20 }));
  });
  const tip = view.container.querySelector('[role="status"]');
  expect(tip).toBeTruthy();
  expect(tip.textContent).toContain('Opened');
  expect(tip.textContent).toMatch(/\d/);
});

test('line chart tooltip flips left on the last points', () => {
  const view = mount(
    <LineChart
      series={[
        {
          key: 'opened',
          label: 'Opened',
          color: '#ff0',
          points: [1, 2, 3, 4, 5, 6],
          labels: ['A', 'B', 'C', 'D', 'E', 'F']
        }
      ]}
    />
  );
  const svg = view.container.querySelector('svg');
  svg.getBoundingClientRect = () => ({ width: 520, height: 180, left: 0, top: 0, right: 520, bottom: 180 });
  act(() => {
    svg.dispatchEvent(new MouseEvent('mousemove', { bubbles: true, clientX: 510, clientY: 20 }));
  });
  const tip = view.container.querySelector('[role="status"]');
  expect(tip).toBeTruthy();
  expect(tip.getAttribute('data-align')).toBe('left');
});

test('dashboard chrome uses Dashboard title without a subtitle', () => {
  const page = readSource('../Dashboard.js');
  expect(page).toContain('title="Dashboard"');
  expect(page).not.toContain('Security Operations Dashboard');
  expect(page).toContain('PageHeader');
  expect(page).toContain('MetricStrip');
  expect(page).toContain('Arrange');
  expect(page).toContain('/apps/');
});

test('line chart primitive is stroke-only with pathLength draw', () => {
  const source = readSource('../../design/primitives/charts.js');
  expect(source).toContain('fill="none"');
  expect(source).toContain('pathLength');
  expect(source).toContain('TRANSITION.draw');
  expect(source).toContain('onMouseMove={pickIndex}');
  expect(source).toContain('<Mono>{item.value}</Mono>');
  expect(source).toContain('n - 3');
});

test('trend widget plots currently active stock under opened vs closed', () => {
  const source = readSource('./components/TrendWidget.js');
  expect(source).toContain('Currently active');
  expect(source).toContain('openStock');
});

test('list widgets paginate coverage, workload, apps, and recent', () => {
  expect(readSource('./components/CoverageGapsWidget.js')).toContain('COVERAGE_PAGE_SIZE');
  expect(readSource('./components/TesterWorkloadWidget.js')).toContain('WORKLOAD_PAGE_SIZE');
  expect(readSource('./components/AppsAtRiskWidget.js')).toContain('APPS_PAGE_SIZE');
  expect(readSource('./components/RecentActivityWidget.js')).toContain('RECENT_PAGE_SIZE');
});
