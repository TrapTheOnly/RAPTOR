const readSource = (relativePath) =>
  require('fs').readFileSync(require('path').join(__dirname, relativePath), 'utf8');

const RESTYLED = [
  '../AdminSettings.js',
  './constants.js',
  './components/SettingsShell.js',
  './components/SettingsNav.js',
  './components/SectionHeader.js',
  './components/AuthTypeChip.js',
  './components/OptionalPermissionControls.js',
  './components/SecuritySection.js',
  './components/DomainsManagementSection.js',
  './components/DomainsRefreshCard.js',
  './components/CollectorsSection.js',
  './components/CollectorsTopology.js',
  './components/IpSourcesSection.js',
  './components/CloudDnsSection.js',
  './components/ReportTemplatesSection.js',
  './components/AiScannerSection.js',
  './components/AiConnectionsPanel.js',
  './components/AiLocalModelPanel.js',
  './components/AiPolicyPanel.js',
  './components/users/UserManagementSection.js',
  './components/users/ExistingUsersPanel.js',
  './components/users/DomainUsersPanel.js',
  './components/users/LocalUsersPanel.js',
  './components/users/ServiceAccountsPanel.js'
];

test('restyled settings files use Operator Console primitives', () => {
  RESTYLED.forEach((file) => {
    const source = readSource(file);
    expect(source).not.toContain('<Select');
    expect(source).not.toContain('<Autocomplete');
    expect(source).not.toContain('<TextField');
    expect(source).not.toContain('<InputLabel');
    expect(source).not.toContain('<Dialog');
    expect(source).not.toContain('<Card');
  });
});

test('settings shell uses Page chrome with in-page nav and tabs', () => {
  const page = readSource('../AdminSettings.js');
  expect(page).toContain("from '../design/primitives'");
  expect(page).toContain('<Page>');
  expect(page).toContain('<PageHeader');
  expect(page).toContain('<SettingsNav');
  expect(page).toContain('<SettingsShell');
  expect(page).toContain('<Toast');
  expect(page).toContain('<Progress deferred');
  expect(page).not.toContain('window.confirm(`Are you sure you want to delete user');
  expect(page).toContain("'/existing-users'");
  expect(page).toContain("'/change-password'");
  expect(page).toContain("'/ip-sources'");
  expect(readSource('./components/CollectorsSection.js')).toContain("'/admin/collectors'");
});

test('user and domain subpages exist in both nested nav and right-side tabs', () => {
  const constants = readSource('./constants.js');
  expect(constants).toContain("key: 'existing'");
  expect(constants).toContain("key: 'add-domain'");
  expect(constants).toContain("key: 'local'");
  expect(constants).toContain("key: 'service-accounts'");
  expect(constants).toContain("key: 'collectors'");
  expect(constants).toContain("key: 'cloud'");
  expect(constants).toContain("key: 'ip-sources'");

  const nav = readSource('./components/SettingsNav.js');
  expect(nav).toContain('USER_SUBSECTIONS');
  expect(nav).toContain('domainTabs');
  expect(nav).toContain("onSelectSection('users')");
  expect(nav).toContain("onSelectSection('domains')");
  expect(nav).toContain('AI_SCANNER_SUBSECTIONS');
  expect(nav).toContain("onSelectSection('ai-scanner')");

  const users = readSource('./components/users/UserManagementSection.js');
  expect(users).toContain('<Tabs');
  expect(users).toContain('USER_SUBSECTIONS');
  expect(users).toContain('raptor-users-split');
  expect(users).toContain('align-items: stretch');
  expect(users).toContain('raptor-users-pane');
  expect(users).toContain('raptor-users-cards');

  const existing = readSource('./components/users/ExistingUsersPanel.js');
  expect(existing).toContain('raptor-users-cards');
  expect(existing).toContain('raptor-users-icon-btn');
  expect(existing).toContain('EditOutlined');
  expect(existing).toContain('DeleteOutline');
  expect(existing).toContain('PAGE_SIZE');
  expect(existing).toContain('variant="outlined"');
  expect(existing).toContain('placeholder="Name, username, role"');
  expect(existing).not.toContain('roleMeta.description');
  expect(existing).not.toContain('>Edit<');
  expect(existing).not.toContain('>Delete<');

  expect(users).toContain('repeat(3, minmax(0, 1fr))');
  expect(users).toContain('raptor-users-icon-btn:hover');
  expect(users).toContain('raptor-users-icon-btn:active');

  const local = readSource('./components/users/LocalUsersPanel.js');
  expect(local).toContain('raptor-users-split');
  expect(local).not.toContain('getRoleMeta');

  const service = readSource('./components/users/ServiceAccountsPanel.js');
  expect(service).toContain('raptor-users-split');
  expect(service).toContain('Create one on the left.');

  const collectors = readSource('./components/CollectorsSection.js');
  expect(collectors).toContain('OsMark');
  expect(collectors).toContain('startIcon={<OsMark type="linux" />}');
  expect(collectors).toContain('startIcon={<OsMark type="windows" />}');
  expect(collectors).toContain('Install an agent on each DNS host and enroll it with a token.');
  expect(collectors).not.toContain('Keep <Mono>raptor-collector run</Mono>');

  const refresh = readSource('./components/DomainsRefreshCard.js');
  expect(refresh).toContain('Run update');
  expect(refresh).not.toContain('Agents parse BIND');

  const domains = readSource('./components/DomainsManagementSection.js');
  expect(domains).toContain('<Tabs');
  expect(domains).toContain('DOMAIN_SUBSECTIONS');
  expect(domains).toContain("tab === 'collectors'");
  expect(domains).toContain("tab === 'ip-sources'");

  const cloudDns = readSource('./components/CloudDnsSection.js');
  expect(cloudDns).toContain('ProviderMark');
  expect(cloudDns).toContain('leading={<ProviderMark type={source.type} size={20} />}');
  expect(cloudDns).toContain("from '../../../design/primitives'");
  expect(cloudDns).not.toContain('Pull connectors for Cloudflare');
  expect(cloudDns).not.toContain('Zone.DNS Read');

  const ipSources = readSource('./components/IpSourcesSection.js');
  expect(ipSources).not.toContain('Labels are network ownership');
  expect(ipSources).toContain('SOURCE_MARKS');

  const brands = readSource('../../design/primitives/brands.js');
  expect(brands).toContain("@lobehub/icons/es/");
  expect(brands).toContain('CloudflareColor');
  expect(brands).toContain('AzureColor');
  expect(brands).toContain('GoogleCloudColor');
  expect(brands).toContain('AlibabaCloudColor');
  expect(brands).toContain('MicrosoftColor');
  expect(brands).toContain('OsMark');

  expect(constants).toContain("key: 'connections'");
  expect(constants).toContain("key: 'policy'");
  expect(constants).toContain('AI_SCANNER_SUBSECTIONS');

  const ai = readSource('./components/AiScannerSection.js');
  expect(ai).toContain('AI_SCANNER_SUBSECTIONS');
  expect(ai).toContain("tab === 'connections'");
  expect(ai).toContain("tab === 'local'");
  expect(readSource('./components/AiConnectionsPanel.js')).toContain('/admin/llm/connections');
  expect(readSource('./components/AiLocalModelPanel.js')).toContain('/admin/llm/local');
  expect(readSource('./components/AiPolicyPanel.js')).toContain('Save policy');

  const reportUtils = readSource('./report-template-utils.js');
  expect(reportUtils).toContain('table_of_contents');
  expect(reportUtils).not.toContain("token: '{{package}}'");
  expect(reportUtils).not.toContain("key: 'package'");
  expect(readSource('./components/report-templates/ReportTemplatePaperPreview.js')).toContain('SEVERITY_CELL');
  expect(readSource('./components/report-templates/ReportTemplatePaperPreview.js')).toContain('overflowWrap');
  expect(readSource('./components/report-templates/ReportTemplatePaperPreview.js')).toContain('#DC2626');
  expect(readSource('./components/report-templates/ReportTemplatePaperPreview.js')).toContain('block.show_logo');
  expect(readSource('./components/ReportTemplatesSection.js')).toContain('Template info');
  expect(readSource('./components/ReportTemplatesSection.js')).toContain('Edit template');
  expect(readSource('./components/ReportTemplatesSection.js')).toContain("formDirty ? 'Save changes' : 'Saved'");
  expect(readSource('./components/ReportTemplatesSection.js')).toContain("width: '100%'");
  expect(readSource('./components/ReportTemplatesSection.js')).toContain('Discard template edits?');
  expect(readSource('./components/ReportTemplatesSection.js')).toContain('placeholders.prepared_for');
  expect(readSource('./components/report-templates/VariablePicker.js')).toContain('AnimatePresence');
  expect(readSource('./components/report-templates/VariablePicker.js')).toContain('Category');
  expect(readSource('./components/report-templates/TemplateEditorCanvas.js')).toContain('Library');
});
