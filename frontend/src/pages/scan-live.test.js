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
