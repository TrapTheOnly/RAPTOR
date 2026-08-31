import React from 'react';
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import ExportSheetDialog from './ExportSheetDialog';
import FindingCard from './FindingCard';
import TicketDialog from './TicketDialog';
import FindingsDashboardTab, { buildStats, waveCoversEnv } from './FindingsDashboardTab';

// react-router-dom v7 ships exports that CRA's Jest resolver cannot load.
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

jest.mock('../services', () => ({
  getEnvAcl: () => Promise.resolve({ data: { usernames: [] } }),
  putEnvAcl: () => Promise.resolve({ data: { usernames: [] } })
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const theme = createTheme();

const readSource = (relativePath) =>
  require('fs').readFileSync(require('path').join(__dirname, relativePath), 'utf8');

// React tracks input values through a property setter, so assigning `.value`
// directly does not fire onChange.
const typeInto = (element, value) => {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  act(() => {
    setter.call(element, value);
    element.dispatchEvent(new Event('input', { bubbles: true }));
  });
};

const mountedViews = [];

const mount = (ui) => {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root = createRoot(container);
  act(() => {
    root.render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
  });
  let alive = true;
  const view = {
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

afterEach(() => {
  while (mountedViews.length) {
    mountedViews.pop().unmount();
  }
});

const ENVIRONMENTS = [
  { id: 1, slug: 'prod', display_name: 'Production', include_in_exec_report: true, is_production: true },
  { id: 2, slug: 'qa', display_name: 'QA', include_in_exec_report: false },
  { id: 3, slug: 'unassigned', display_name: 'Unassigned' }
];

test('owner delivery sheet defaults prod env checked and drafts stay off', () => {
  const view = mount(
    <ExportSheetDialog
      open
      onClose={() => {}}
      environments={ENVIRONMENTS}
      defaultEnvIds={[1]}
      canExport
      generating={false}
      onGenerate={() => {}}
    />
  );

  expect(document.body.textContent).toContain('Export sheet');
  expect(document.body.textContent).toContain('Production only, drafts off');
  expect(document.body.textContent).toContain('Production');
  expect(document.body.textContent).toContain('QA');
  expect(document.body.textContent).not.toContain('Unassigned');
  view.unmount();
});

test('export sheet offers the four named packages on one sheet', () => {
  const source = readSource('./ExportSheetDialog.js');
  const tokens = readSource('../../../theme/tokens.js');
  expect(tokens).toContain('owner_delivery');
  expect(tokens).toContain('wave_archive');
  expect(tokens).toContain('retest_pack');
  expect(tokens).toContain('internal_draft');
  expect(source).toContain('EXPORT_PACKAGES');
  expect(source).toContain('Live preview');
  expect(source).toContain('scopedWave');
  expect(source).not.toContain('End and export');
  expect(source).toContain('does not end the wave');
  expect(source).toContain('Host domain');
  expect(source).toContain('Report template');
  expect(source).toContain('template_id');
  expect(source).not.toContain('Keep hostnames that end');
  expect(source).toContain('I confirm this export scope');
  expect(source).not.toContain('I confirm this pack scope');
  expect(source).not.toContain('Zone suffix');
  expect(source).not.toContain('this pack will contain');
});

test('export sheet requires an explicit scope confirmation before generating', () => {
  const generated = [];
  const view = mount(
    <ExportSheetDialog
      open
      onClose={() => {}}
      environments={ENVIRONMENTS}
      defaultEnvIds={[1]}
      canExport
      generating={false}
      onGenerate={(payload) => generated.push(payload)}
    />
  );

  const generateButton = [...document.querySelectorAll('button')].find((button) =>
    button.textContent.toLowerCase().includes('generate')
  );
  expect(generateButton).toBeTruthy();
  expect(generateButton.disabled).toBe(true);
  expect(generated).toHaveLength(0);
  view.unmount();
});

test('wave-scoped export preselects the wave without ending it', () => {
  const view = mount(
    <ExportSheetDialog
      open
      onClose={() => {}}
      environments={ENVIRONMENTS}
      defaultEnvIds={[1, 2]}
      waves={[{ id: 7, name: '2026 H1', env_ids: [1], status: 'open' }]}
      scopedWave={{ id: 7, name: '2026 H1', env_ids: [1], status: 'open' }}
      canExport
      generating={false}
      onGenerate={() => {}}
    />
  );

  expect(document.body.textContent).toContain('Export sheet');
  expect(document.body.textContent).toContain('does not end the wave');
  expect(document.body.textContent).not.toContain('End and export');
  expect(document.body.textContent).not.toContain('End “2026 H1”');
  expect(document.body.textContent).toContain('I confirm this export scope');
  expect(document.body.textContent).toContain('Host domain');
  expect(document.body.textContent).toContain('Production');
  expect(document.body.textContent).toContain('QA');
  const generateButton = [...document.querySelectorAll('button')].find((button) =>
    button.textContent.toLowerCase().includes('generate')
  );
  expect(generateButton).toBeTruthy();
  expect(generateButton.disabled).toBe(true);
  view.unmount();
});

test('export sheet surfaces the live preview counts and excluded unassigned hosts', async () => {
  const preview = {
    data: {
      finding_count: 3,
      excluded_draft_count: 2,
      watermark: 'PRODUCTION',
      unassigned_in_scope_hosts: [{ record_id: 9, name: 'orphan.google.com' }],
      findings: [{ id: 'f1', title: 'CORS misconfiguration', baseScore: 9.1, also_observed: [] }]
    }
  };

  const view = mount(
    <ExportSheetDialog
      open
      onClose={() => {}}
      environments={ENVIRONMENTS}
      defaultEnvIds={[1]}
      canExport
      generating={false}
      onGenerate={() => {}}
      onPreview={() => Promise.resolve(preview)}
    />
  );

  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 450));
  });

  expect(document.body.textContent).toContain('PRODUCTION');
  expect(document.body.textContent).toContain('CORS misconfiguration');
  expect(document.body.textContent).toContain('orphan.google.com');
  expect(document.body.textContent).toContain('2 drafts excluded');
  view.unmount();
});

test('finding card exposes per-occurrence status so a retest can be queued', () => {
  const finding = {
    id: 'f1',
    title: 'Permissive CORS',
    status: 'open',
    baseScore: 9.1,
    source: 'human',
    description: '# this write-up must not appear in the inbox',
    occurrences: [
      {
        finding_id: 'f1',
        record_id: 1,
        status: 'open',
        dns_name: 'www.google.com',
        environment_slug: 'prod',
        host_status: 'active'
      },
      {
        finding_id: 'f1',
        record_id: 2,
        status: 'retest',
        dns_name: 'qa.google.com',
        environment_slug: 'qa',
        host_status: 'active'
      }
    ]
  };

  const view = mount(
    <FindingCard
      finding={finding}
      canModify
      busy={false}
      defaultExpanded
      onOccurrenceStatusChange={() => {}}
      onOpenTicket={() => {}}
      onOpenMerge={() => {}}
      onPromote={() => {}}
    />
  );

  expect(document.body.textContent).toContain('Permissive CORS');
  expect(document.body.textContent).toContain('Critical 9.1');
  expect(document.body.textContent).toContain('www.google.com');
  expect(document.body.textContent).toContain('qa.google.com');
  expect(document.body.textContent).toContain('2 hosts');
  expect(document.body.textContent).not.toContain('this write-up must not appear in the inbox');
  const comboValues = [...document.querySelectorAll('input')].map((input) => input.value);
  expect(comboValues).toEqual(expect.arrayContaining(['Open', 'Retest']));
  view.unmount();
});

test('finding card marks findings whose hosts have all gone missing', () => {
  const finding = {
    id: 'f2',
    title: 'Stale header',
    status: 'open',
    baseScore: 3.1,
    occurrences: [
      {
        finding_id: 'f2',
        record_id: 5,
        status: 'open',
        dns_name: 'gone.google.com',
        environment_slug: 'prod',
        host_status: 'missing'
      }
    ]
  };

  const view = mount(
    <FindingCard
      finding={finding}
      canModify={false}
      busy={false}
      defaultExpanded
      onOccurrenceStatusChange={() => {}}
      onOpenTicket={() => {}}
      onOpenMerge={() => {}}
      onPromote={() => {}}
    />
  );

  expect(document.body.textContent).toContain('missing');
  view.unmount();
});

test('ticket dialog replaces window.prompt and validates the URL', () => {
  const saved = [];
  const view = mount(
    <TicketDialog
      open
      finding={{ id: 'f1', ticket_url: '' }}
      onClose={() => {}}
      onSave={(value) => saved.push(value)}
    />
  );

  typeInto(document.querySelector('input[placeholder*="jira"]'), 'not-a-url');

  const saveButton = [...document.querySelectorAll('button')].find(
    (button) => button.textContent === 'Save'
  );
  act(() => {
    saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });

  expect(saved).toHaveLength(0);
  expect(document.body.textContent).toContain('http://');

  typeInto(document.querySelector('input[placeholder*="jira"]'), 'https://jira.example.com/browse/SEC-1');
  act(() => {
    saveButton.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });

  expect(saved).toEqual(['https://jira.example.com/browse/SEC-1']);
  view.unmount();
});

test('workspace is tabbed rather than one long scroll, and never uses window.prompt', () => {
  const source = readSource('../../AppWorkspace.js');
  expect(source).toContain('<Tabs');
  ['overview', 'findings', 'hosts', 'waves', 'program'].forEach((tab) => {
    expect(source).toContain(`'${tab}'`);
  });
  expect(source).not.toContain('window.prompt');
  expect(source).toContain('MetricStrip');
  expect(source).toContain('PageHeader');
});

test('app workspace offers Dashboard to leave, env drill-down offers App overview', () => {
  const source = readSource('../../AppWorkspace.js');
  expect(source).toContain('filtered to this environment');
  expect(source).toContain("'env-settings'");
  expect(source).toContain('/apps/${appId}');
  expect(source).toContain('App overview');
  expect(source).toContain('to="/pentest"');
  expect(source).toContain('Dashboard');
  const overview = readSource('./OverviewTab.js');
  expect(overview).toContain('selected={String(env.id) === String(envId)}');
  expect(overview).toContain('LAYOUT_ID.envCoverageRail');
  expect(overview).toContain("envId ? 'Manage environment' : 'Manage environments'");
  expect(overview).toContain("envId ? 'env-settings' : 'environments'");
  expect(overview).toContain('Open risk');
  expect(overview).toContain("alignItems: 'start'");
  expect(overview).toContain('No open or retest findings');
  expect(overview).toContain('No wave open');
  expect(overview).toContain('SeverityTrack');
  expect(overview).not.toContain('Highest risk right now');
  expect(overview).toContain('No hosts filed yet');
  expect(overview).not.toContain('No environments yet');
});

test('environments list can delete seeded rows except unassigned', () => {
  const source = readSource('./EnvironmentsTab.js');
  expect(source).not.toContain('TEMPLATE_SLUGS');
  expect(source).toContain("env.slug === 'unassigned'");
  expect(source).toContain('DeleteOutline');
  expect(source).toContain('aria-label={`Delete ${env.display_name}`}');
  expect(source).toContain('Delete environment');
  expect(source).toContain('Confirm delete');
  expect(source).not.toContain('notification for 5 seconds');
  const workspace = readSource('../../AppWorkspace.js');
  expect(workspace).toContain("actionLabel: 'Revert'");
  expect(workspace).toContain('duration: 5000');
  expect(workspace).toContain('revertPendingDelete');
  const toast = readSource('../../../design/primitives/chrome.js');
  expect(toast).toContain('actionLabel, onAction');
});

test('new finding host picker searches the app, not the hosts-tab page', () => {
  const source = readSource('./NewFindingDialog.js');
  expect(source).toContain('HostPicker');
  expect(source).toContain('lockedHost');
  expect(source).toContain('label="Impact"');
  expect(source).toContain('label="Evidence"');
  expect(source).toContain('label="Remediation"');
  expect(source).not.toContain('blastOptions');
  const picker = readSource('./HostPicker.js');
  expect(picker).toContain('listAppHosts');
  expect(picker).toContain('limit: 20');
  const workspace = readSource('../../AppWorkspace.js');
  expect(workspace).toContain('form.record_ids || []');
  expect(workspace).toContain('String(form.record_id)');
  expect(workspace).toContain('impact: form.impact');
  expect(workspace).toContain('AttachHostsDialog');
  expect(workspace).not.toContain('if (!targetEnv) return');
});

test('finding ticket icon only follows http(s) URLs', () => {
  const source = readSource('./FindingCard.js');
  expect(source).toContain('isHttpUrl');
  expect(source).toContain('ticketIsLink');
  expect(source).not.toContain('href={finding.ticket_url}');
  expect(source).not.toContain('finding.description');
});

test('hosts tab is inventory; wave header launches scans', () => {
  const hosts = readSource('./HostsTab.js');
  expect(hosts).not.toContain('Launch scan');
  expect(hosts).not.toContain('onLaunchScan');
  const wavePage = readSource('./WaveDetailTab.js');
  expect(wavePage).toContain('Launch scan');
  expect(wavePage).toContain('onLaunchScan');
  expect(wavePage).toContain('/scan-live');
  expect(wavePage).not.toContain('onLaunchScan(host)');
  expect(wavePage).toContain('`Hosts (${hosts.length})`');
  expect(wavePage).toContain('`Findings (${findings.length})`');
  expect(wavePage).toContain('End wave');
  expect(wavePage).toContain('onExportWave');
  expect(wavePage).toContain('Start wave');
  expect(wavePage).not.toContain('End and export');
  expect(wavePage).not.toContain('Archive pack');
  expect(wavePage).not.toContain('Close wave');
  expect(wavePage).toContain('New finding');
  expect(wavePage).toContain('startIcon={<Add');
  expect(wavePage).toContain('FileDownload');
  expect(wavePage).toContain('StopCircle');
  expect(wavePage).toContain('jiraReportable');
  expect(wavePage).toContain('disabled={!jiraReportable}');
  expect(wavePage).toContain('dojoReportable');
  expect(wavePage).toContain('disabled={!dojoReportable}');
  expect(wavePage).toContain('Report to Jira');
  expect(wavePage).toContain('Report to DefectDojo');
  expect(wavePage).toContain('onReportToIntegration');
  expect(wavePage).toContain('BurpLiveSection');
  expect(readSource('./BurpLiveSection.js')).toContain('Burp Live');
  expect(readSource('./BurpLiveSection.js')).toContain('Mint wave token');
  expect(readSource('./BurpLiveSection.js')).toContain('/burp/v1/download/raptor-burp.jar');
  expect(readSource('./BurpLiveSection.js')).toContain('Start happens in Burp');
  expect(readSource('../services.js')).toContain('burp-token');
  expect(readSource('../services.js')).toContain('/engagements');
  expect(readSource('./BurpLiveSection.js')).toContain('Summarize Burp traffic');
  expect(readSource('./BurpLiveSection.js')).toContain('startBurpAnalyze');
  expect(readSource('../services.js')).toContain('/burp/analyze');
  const header = readSource('../../pentest-record/components/PentestRecordHeader.js');
  expect(header).not.toContain('Launch AI Scan');
  expect(header).not.toContain('launchAiScan');
  expect(header).toContain('AI scan');
  expect(header).toContain('/scan-live');
  expect(header).toContain('App overview');
});

test('host notebook uses Operator Console primitives and does not edit findings', () => {
  const files = [
    '../../pentest-record/components/PentestRecordHeader.js',
    '../../pentest-record/components/PentestRecordTabs.js',
    '../../pentest-record/components/PentestRecordSidebar.js',
    '../../pentest-record/components/OverviewTab.js',
    '../../pentest-record/components/FindingsTab.js',
    '../../pentest-record/components/ChecklistTab.js',
    '../../pentest-record/components/MarkdownEditorCard.js',
    '../../PentestRecord.js'
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
  const record = readSource('../../PentestRecord.js');
  expect(record).toContain("from '../design/primitives'");
  expect(record).not.toContain('launchAiScan');
  expect(record).not.toContain('handleLaunchScan');
  expect(record).toContain('fetchPentestRecord');
  expect(record).not.toContain('JSON.stringify(vulnerabilities)');
  expect(record).toContain("searchParams.get('wave')");
  expect(record).toContain('closedWaveIds');
  const findings = readSource('../../pentest-record/components/FindingsTab.js');
  expect(findings).toContain('No findings on this host');
  expect(findings).toContain('File finding on this host');
  expect(findings).toContain('findingFrozen');
  expect(findings).toContain('closedWaveIds');
  const overview = readSource('../../pentest-record/components/OverviewTab.js');
  expect(overview).not.toContain('Test Management');
  expect(overview).not.toContain('service_desk');
  expect(overview).not.toContain('test_start_date');
  expect(overview).not.toContain('Host report');
  expect(overview).not.toContain('Download generated');
  const waves = readSource('./WavesTab.js');
  expect(waves).toContain('one or more environments');
  expect(waves).toContain('env_ids');
  expect(waves).toContain('live hosts');
  expect(waves).toContain('End wave');
  expect(waves).toContain('onExport');
  expect(waves).not.toContain('End and export');
  expect(waves).not.toContain('Archive pack');
  expect(waves).not.toContain('Close wave');
  const checklist = readSource('../../pentest-record/components/ChecklistTab.js');
  expect(checklist).not.toContain('SwitchRow');
  expect(checklist).toContain('Add checklist');
  const appSource = readSource('../../../App.js');
  expect(appSource).toContain('path="waves/:waveId"');
  expect(appSource).toContain('path="findings/:findingId"');
  const workspace = readSource('../../AppWorkspace.js');
  expect(workspace).not.toContain('wave-detail');
  expect(workspace).toContain('FindingPage');
  expect(workspace).toContain("label: 'Findings'");
  expect(workspace).not.toContain('Findings${');
  expect(workspace).not.toContain('New finding');
  expect(workspace).toContain('openExportWave');
  expect(workspace).toContain('scopedWave={scopedWave}');
  expect(workspace).not.toContain('openEndWave');
  expect(workspace).not.toContain('lockedWave');
  const findingPage = readSource('./FindingPage.js');
  expect(findingPage).toContain('CvssCalculator');
  expect(findingPage).toContain('MarkdownEditorCard');
  expect(findingPage).toContain('uploadPentestImage');
  expect(findingPage).toContain('Collaborators');
  expect(findingPage).toContain('data?.categories');
  expect(findingPage).toContain('FactChip');
  expect(findingPage).toContain('showActions={false}');
  expect(findingPage).toContain('canEdit = Boolean(canModify && waveIsOpen)');
  expect(findingPage).toContain('This wave has ended');
  expect(findingPage).toContain('title="Impact"');
  expect(findingPage).toContain('title="Evidence"');
  expect(findingPage).toContain('title="Remediation"');
  expect(findingPage).toContain('Delete finding');
  expect(findingPage).toContain('deleteFinding');
  expect(findingPage).not.toContain('Found here ·');
  expect(readSource('./CvssCalculator.js')).toContain('CVSS 3.1');
  const hostFindings = readSource('../../pentest-record/components/FindingsTab.js');
  expect(hostFindings).toContain('/findings/');
  const wavePage = readSource('./WaveDetailTab.js');
  expect(wavePage).toContain('Live hosts from the environments');
  expect(wavePage).not.toContain('EnvironmentSettingsTab');
  expect(wavePage).toContain('Assign to me');
  expect(wavePage).toContain('Mark in scope');
  expect(wavePage).toContain('Notebook');
  expect(wavePage).toContain('hostNotebookPath(host.id, wave.id)');
  expect(readSource('./ProgramTab.js')).not.toContain('/pentest/record/');
  expect(readSource('./FindingCard.js')).toContain('hostNotebookPath');
  expect(readSource('../../PentestRecord.js')).toContain('if (!engagementWaveId)');
  expect(wavePage).toContain('disabled={!canModify || !isOpen}');
  expect(wavePage).toContain('canModify={canModify && isOpen}');
  expect(wavePage).toContain('This wave has ended');
  expect(readSource('../../pentest-record/components/MarkdownEditorCard.js')).toContain('max-width: 100%');
  expect(readSource('../../pentest-record/components/MarkdownEditorCard.js')).toContain('.raptor-md-preview blockquote');
  expect(readSource('../../pentest-record/components/MarkdownEditorCard.js')).toContain('width: 100%');
  expect(readSource('../../pentest-record/components/MarkdownEditorCard.js')).toContain('HttpExchange');
  expect(readSource('../../pentest-record/components/HttpExchange.js')).toContain('raptor-http-exchange');
  expect(readSource('../../pentest-record/components/HttpExchange.js')).toContain("split(/^\\s*===\\s*$/m)");
  expect(readSource('../../pentest-record/components/HttpExchange.js')).toContain('twoCol');
  expect(readSource('./HostsTab.js')).toContain('Add hosts');
  expect(readSource('./HostsTab.js')).not.toContain('Assign tester');
  expect(readSource('./HostsTab.js')).not.toContain('allInScope');
  expect(readSource('./EnvironmentSettingsTab.js')).not.toContain('waveMode');
  expect(readSource('./EnvironmentSettingsTab.js')).not.toContain('in_scope_urls');
  expect(readSource('./MergeFindingsDialog.js')).toContain('impact, evidence, and remediation fill from');
  const appOverview = readSource('./OverviewTab.js');
  expect(appOverview).not.toContain('still unassigned');
  expect(appOverview).not.toContain('File them into an environment');
  expect(appOverview).not.toContain('onFileUnassigned');
  expect(appOverview).not.toContain('% in scope');
  expect(readSource('./FindingsDashboardTab.js')).toContain('Active and fixed over time');
  expect(readSource('./FindingsDashboardTab.js')).toContain('Recent by severity');
  expect(readSource('./FindingsDashboardTab.js')).toContain("gridColumn: envId ? 'span 3' : 'span 2'");
  expect(readSource('./FindingsDashboardTab.js')).toContain('preserveAspectRatio="none"');
  expect(readSource('./FindingsDashboardTab.js')).toContain('onMouseMove={pickIndex}');
  expect(readSource('./FindingsDashboardTab.js')).toContain('TRANSITION.draw');
  expect(readSource('./FindingsDashboardTab.js')).toContain('Week of');
  expect(readSource('./ProgramTab.js')).toContain('Host domains');
});

test('environment settings keep standing RoE and the scan ceiling', () => {
  const source = readSource('./EnvironmentSettingsTab.js');
  [
    'contacts',
    'data_class',
    'test_window',
    'creds_vault_pointer',
    'include_in_exec_report',
    'allow_destructive',
    'max_concurrent_scans',
    'roe_text',
    'getEnvAcl',
    'putEnvAcl'
  ].forEach((field) => {
    expect(source).toContain(field);
  });
  expect(source).toContain('Open to anyone with pentest view');
  expect(source).toContain('canManage');
  expect(source).not.toContain('in_scope_urls');
  expect(source).not.toContain('out_of_scope_urls');
  expect(source).not.toContain('Contractor access');
  expect(source).not.toContain('Checklists');
});

test('workspace screens share Field, Combo, and Panel instead of mixed MUI menus', () => {
  const files = [
    'FindingsInboxTab.js',
    'FindingsDashboardTab.js',
    'HostsTab.js',
    'WavesTab.js',
    'EnvironmentsTab.js',
    'EnvironmentSettingsTab.js',
    'ProgramTab.js',
    'OverviewTab.js',
    'ExportSheetDialog.js',
    'NewFindingDialog.js',
    'TicketDialog.js',
    'ShareHostDialog.js',
    'MergeFindingsDialog.js',
    'WaveDetailTab.js',
    'AttachHostsDialog.js',
    'HostPicker.js',
    'FindingCard.js',
    'FindingPage.js',
    'CvssCalculator.js',
    'ExportIntegrationWizard.js'
  ];
  files.forEach((file) => {
    const source = readSource(`./${file}`);
    expect(source).not.toContain('<Select');
    expect(source).not.toContain('<Autocomplete');
    expect(source).not.toContain('<TextField');
    expect(source).not.toContain('<InputLabel');
    expect(source).not.toContain('SectionCard');
    expect(source).not.toContain('<Dialog');
  });
});

test('findings toolbar keeps a fixed track so filters cannot wrap the row', () => {
  const source = readSource('./FindingsInboxTab.js');
  expect(source).toContain('gridTemplateColumns');
  expect(source).toContain("visibility: hasFilters ? 'visible' : 'hidden'");
  expect(source).toContain("whiteSpace: 'nowrap'");
});

test('dialogs tint the page behind the panel', () => {
  const chrome = readSource('../../../design/primitives/chrome.js');
  expect(chrome).toContain('slots={{ backdrop: PanelScrim }}');
  expect(chrome).toContain('backgroundColor: palette.scrim');
  const theme = readSource('../../../design/theme.js');
  expect(theme).toContain('MuiBackdrop');
  expect(theme).toContain('p.scrim');
  expect(theme).toContain('hideBackdrop: false');
});

test('menus use a short Fade and an invisible click-catcher so they dismiss', () => {
  const theme = readSource('../../../design/theme.js');
  expect(theme).toContain('TransitionComponent: Fade');
  expect(theme).toContain('slotProps: { backdrop: { invisible: true } }');
  expect(theme).not.toContain('hideBackdrop: true');
  expect(theme).not.toContain('MenuTransition');
  expect(theme).not.toContain('DropdownPopper');
  const combo = readSource('../../../design/primitives/combo.js');
  expect(combo).not.toContain('DropdownPopper');
});

test('workspace seeds from the dashboard preview so opening an app does not blank', () => {
  const source = readSource('../../AppWorkspace.js');
  expect(source).toContain('peekAppPreview');
  expect(source).toContain('location.state?.app');
  expect(source).not.toContain('Loading application workspace');
});

test('app workspace is one shell: /apps/:appId with nested envs/:envId', () => {
  const appSource = readSource('../../../App.js');
  expect(appSource).toContain('path="/apps/:appId"');
  expect(appSource).toContain('path="envs/:envId"');
  expect(appSource).toContain('path="waves/:waveId"');
  expect(appSource).toContain('path="findings/:findingId"');
  expect(appSource).toContain('routeShellKey');
  expect(appSource).not.toContain('key={location.pathname}');
  expect(appSource).not.toContain('mode="wait"');
  expect(appSource).not.toContain('AnimatePresence');
  expect(appSource).toContain('path="/pentest"');
  expect(appSource).toContain('path="/pentest/record/:recordId"');
  const appsBlock = appSource.split('path="/apps/:appId"')[1].slice(0, 500);
  expect(appsBlock).toContain("hasPermission('view_pentest_page')");
  expect(appsBlock).not.toContain("hasPermission('view_security_dashboard')");
  const recordsBlock = appSource.split('path="/records"')[1].split('<Route')[0];
  expect(recordsBlock).toContain('getDefaultRoute()');
  const pentestBlock = appSource.split('path="/pentest"')[1].split('<Route')[0];
  expect(pentestBlock).toContain("hasPermission('view_security_dashboard')");
  expect(pentestBlock).toContain('getDefaultRoute()');
});

test('waves tab shows a count and env drill-down only lists waves that cover that env', () => {
  const workspace = readSource('../../AppWorkspace.js');
  expect(workspace).toContain('Waves (${envWaves.length})');
  expect(workspace).toContain('waveCoversEnv');
  expect(workspace).toContain('waves={envWaves}');
  expect(waveCoversEnv({ env_ids: [3, 8] }, 8)).toBe(true);
  expect(waveCoversEnv({ env_ids: [3, 8] }, 1)).toBe(false);
  expect(waveCoversEnv({ environment_id: 4 }, 4)).toBe(true);
  expect(waveCoversEnv({ environment_id: 4 }, 5)).toBe(false);
});

test('env findings dashboard hides per-environment and scopes charts to that env', () => {
  const now = new Date('2026-08-19T12:00:00');
  const findings = [
    {
      id: 'in-env',
      title: 'XSS',
      status: 'open',
      baseScore: 7.5,
      created_at: now.toISOString(),
      discovered_wave_id: 1,
      occurrences: [
        { environment_id: 1, environment_slug: 'qa', status: 'open', created_at: now.toISOString() },
        { environment_id: 2, environment_slug: 'prod', status: 'fixed', created_at: now.toISOString() }
      ]
    },
    {
      id: 'other-env',
      title: 'SQLi',
      status: 'open',
      baseScore: 9.8,
      created_at: now.toISOString(),
      discovered_wave_id: 9,
      occurrences: [{ environment_id: 2, environment_slug: 'prod', status: 'open', created_at: now.toISOString() }]
    }
  ];
  const waves = [
    { id: 1, name: 'QA wave', env_ids: [1], members: ['ada'] },
    { id: 9, name: 'Prod only', env_ids: [2], members: ['bob'] }
  ];
  const stats = buildStats(findings, waves, ENVIRONMENTS, { envId: 1, now });
  expect(stats.total).toBe(1);
  expect(stats.perWave.map((item) => item.label)).toEqual(['QA wave']);
  expect(stats.testersPerWave.map((item) => item.label)).toEqual(['QA wave']);
  expect(stats.occStatus).toEqual([{ key: 'open', label: 'open', value: 1 }]);
  expect(stats.overTime[stats.overTime.length - 1].active).toBe(1);
  expect(stats.overTime[stats.overTime.length - 1].fixed).toBe(0);

  const view = mount(
    <FindingsDashboardTab envId={1} appId={1} findings={findings} waves={waves} environments={ENVIRONMENTS} />
  );
  expect(document.body.textContent).not.toContain('Findings per environment');
  expect(document.body.textContent).toContain('Findings per wave');
  expect(document.body.textContent).toContain('QA wave');
  expect(document.body.textContent).not.toContain('Prod only');
  view.unmount();
});

test('active and fixed over time freezes last week when that week is fully remediated', () => {
  const now = new Date('2026-08-19T12:00:00');
  const detected = new Date('2026-08-04T10:00:00');
  const findings = Array.from({ length: 11 }, (_, index) => ({
    id: `f${index}`,
    status: 'fixed',
    baseScore: 5,
    created_at: detected.toISOString(),
    updated_at: now.toISOString(),
    discovered_wave_id: 1,
    occurrences: [
      {
        environment_id: 1,
        status: 'fixed',
        created_at: detected.toISOString(),
        status_changed_at: detected.toISOString(),
        updated_at: now.toISOString()
      }
    ]
  }));
  const stats = buildStats(findings, [{ id: 1, name: 'Wave', members: [] }], ENVIRONMENTS, { now });
  const current = stats.overTime[stats.overTime.length - 1];
  const previous = stats.overTime[stats.overTime.length - 2];
  expect(previous.active).toBe(0);
  expect(previous.fixed).toBe(11);
  expect(current.active).toBe(0);
  expect(current.fixed).toBe(11);
  const beforeDetection = stats.overTime[stats.overTime.length - 4];
  expect(beforeDetection.active + beforeDetection.fixed).toBe(0);
});

const SECRET_ENV = {
  id: 1,
  slug: 'prod',
  display_name: 'Production',
  roe_text: 'SECRET_ROE_TEXT',
  creds_vault_pointer: 'vault://secret-pointer',
  contacts: 'security@example.com'
};

test('environment settings hide RoE and vault pointer from viewers', async () => {
  const EnvironmentSettingsTab = require('./EnvironmentSettingsTab').default;
  const view = mount(
    <EnvironmentSettingsTab
      appId={1}
      env={SECRET_ENV}
      canManage={false}
      pentestUsers={['ada']}
      onSaveEnvironment={() => {}}
    />
  );

  await act(async () => {
    await Promise.resolve();
  });

  expect(document.body.textContent).toContain('prod');
  expect(document.body.textContent).toContain('Open to anyone with pentest view');
  expect(document.body.textContent).not.toContain('SECRET_ROE_TEXT');
  expect(document.body.textContent).not.toContain('vault://secret-pointer');
  expect(document.body.textContent).not.toContain('Rules of engagement');
  expect(document.body.textContent).not.toContain('Credentials vault pointer');
  view.unmount();
});

test('environment settings show RoE to managers and load ACL', async () => {
  const EnvironmentSettingsTab = require('./EnvironmentSettingsTab').default;
  const view = mount(
    <EnvironmentSettingsTab
      appId={1}
      env={SECRET_ENV}
      canManage
      pentestUsers={['ada']}
      onSaveEnvironment={() => {}}
    />
  );

  await act(async () => {
    await Promise.resolve();
  });

  expect(document.body.textContent).toContain('SECRET_ROE_TEXT');
  expect(document.body.textContent).toContain('Rules of engagement');
  expect(document.body.textContent).toContain('Credentials vault pointer');
  expect(document.body.textContent).toContain('Environment access');
  expect(document.body.textContent).toContain('Open to anyone with pentest view');
  const vault = document.querySelector('input[placeholder="Path or URL — never paste a secret here"]');
  expect(vault).toBeTruthy();
  expect(vault.value).toBe('vault://secret-pointer');
  view.unmount();
});

test('finding page and workspace open the integration wizard', () => {
  const findingPage = readSource('./FindingPage.js');
  expect(findingPage).toContain('Report to Jira');
  expect(findingPage).toContain('Report to DefectDojo');
  expect(findingPage).toContain('Open ticket');
  expect(findingPage).toContain('Open in DefectDojo');
  expect(findingPage).toContain('defectdojo_url');
  expect(findingPage).toContain('isHttpUrl');
  expect(findingPage).not.toContain('Edit ticket');
  expect(findingPage).not.toContain('Link ticket');
  expect(findingPage).toContain('onReportToIntegration');
  const workspace = readSource('../../AppWorkspace.js');
  expect(workspace).toContain('ExportIntegrationWizard');
  expect(workspace).toContain('listReadyIntegrations');
  const wizard = readSource('./ExportIntegrationWizard.js');
  expect(wizard).toContain('previewIntegrationExport');
  expect(wizard).toContain('exportToIntegration');
  expect(wizard).toContain('Filled from RAPTOR');
  expect(wizard).toContain('already_exported');
  expect(wizard).toContain('flexDirection: \'column\'');
  expect(wizard).not.toContain('will create another ticket');
  expect(wizard).toContain('!waveId && (data.findings || []).length === 1');
});
