const fs = require('fs');
const path = require('path');

const readSource = (relativePath) =>
  fs.readFileSync(path.join(__dirname, relativePath), 'utf8');

test('ScanLive is the wave Operator Console', () => {
  const source = readSource('./ScanLive.js');
  expect(source).toContain("from '../design/primitives'");
  expect(source).toContain('<Page>');
  expect(source).toContain('<PageHeader');
  expect(source).toContain('<EmptyState');
  expect(source).toContain('launchWaveScan');
  expect(source).toContain('resetWaveScan');
  expect(source).toContain('stopWaveScan');
  expect(source).toContain('Launch scan');
  expect(source).toContain('Restart scan');
  expect(source).toContain('Stop scan');
  expect(source).toContain('operator_brief');
  expect(source).toContain('Operator notes');
  expect(source).toContain('skip_port_discovery');
  expect(source).toContain('HostChip');
  expect(source).toContain('color-mix');
  expect(source).toContain('input_snippet');
  expect(source).toContain('result_snippet');
  expect(source).toContain('ProviderMark');
  expect(source).toContain('All hosts');
  expect(source).toContain('foldEvents');
  expect(source).toContain('listWaveEngagements');
  expect(source).toContain('EngagementRail');
  expect(source).toContain('BurpEngagementPane');
  expect(source).toContain('title="Live"');
  expect(source).toContain("params.set('engagement'");
  expect(source).toContain("pathname.includes('/scan-live')");
  expect(source).toContain('if (done || viewingBurp)');
  expect(source).not.toContain('setEngagements([])');
  expect(source).toContain('/apps/${appId}/waves/${waveId}/scan-events/stream');
  expect(source).not.toContain('In-scope hosts');
  expect(source).not.toContain('--with-scanner');
  expect(source).not.toContain('launchAiScan');
  expect(source).not.toContain('<Card');
  expect(source).not.toContain('<TextField');
  expect(source).not.toContain('<Dialog');
  expect(source).not.toContain('<Select');
});

test('host notebook links to wave ScanLive but does not POST launch', () => {
  const record = readSource('./PentestRecord.js');
  expect(record).not.toContain('launchAiScan');
  expect(record).not.toContain('handleLaunchScan');
  const header = readSource('./pentest-record/components/PentestRecordHeader.js');
  expect(header).toContain('/scan-live');
  expect(header).not.toContain('launchAiScan');
  expect(header).not.toContain('launchWaveScan');
});

test('Live page lists named engagements in a left rail', () => {
  const rail = readSource('./scan-live/EngagementRail.js');
  expect(rail).toContain('aria-label="Engagements"');
  expect(rail).toContain('names each job before work starts');
  const pane = readSource('./scan-live/BurpEngagementPane.js');
  expect(pane).toContain('Open finding');
  expect(pane).toContain('findingId || hits.length > 0');
  expect(pane).toContain('acceptBurpEngagement');
  expect(pane).toContain('acceptBurpProposal');
  expect(pane).toContain('RAPTOR is naming the job…');
  expect(pane).toContain('No JWT weakness to file');
  expect(pane).toContain("kind === 'scanner'");
  expect(pane).not.toContain('jwt_tool steps');
  expect(pane).not.toContain('This page updates as the worker reports');
});

test('Live analyze pane clusters Burp traffic instead of listing raw events', () => {
  const pane = readSource('./scan-live/AnalyzeEngagementPane.js');
  expect(pane).toContain('What you tried');
  expect(pane).toContain('RAPTOR is naming the job…');
  expect(pane).toContain('Attach HTTP to a draft');
  expect(pane).toContain('you decide what is proof');
  expect(pane).toContain('clusterKey');
  expect(pane).toContain('row.tool');
  expect(pane).toContain('Send JWT from Burp');
  expect(pane).toContain('Propose');
  expect(pane).toContain('HttpExchange');
  expect(pane).toContain('onToggle');
  expect(pane).not.toContain('jwt_tool');
  const live = readSource('./ScanLive.js');
  expect(live).toContain('startBurpAnalyze');
  expect(live).toContain('Summarize Burp traffic');
  expect(live).toContain('AnalyzeEngagementPane');
  expect(live).toContain("startsWith('proposal:')");
  expect(live).not.toContain('maxWidth: 720');
  expect(live).not.toContain('maxWidth: 880');
});
