export const REPORT_CHART_OPTIONS = [
  { value: 'vulnerability_severity', label: 'Vulnerability Severity' },
  { value: 'occurrence_status', label: 'Occurrence Status' },
  { value: 'checklist_completion', label: 'Checklist Completion' },
  { value: 'severity_by_env', label: 'Findings by Environment' },
  { value: 'wave_coverage', label: 'Wave Coverage' }
];

export const REPORT_MARKDOWN_FIELD_OPTIONS = [
  { value: 'description', label: 'Asset Description' },
  { value: 'notes', label: 'Security Details' },
  { value: 'open_ports', label: 'Open Ports Text' }
];

export const OVERVIEW_FIELDS = [
  { key: 'target', label: 'Target hostname', group: 'Host' },
  { key: 'ip', label: 'IP address', group: 'Host' },
  { key: 'source', label: 'Asset source', group: 'Host' },
  { key: 'application', label: 'Application', group: 'Both' },
  { key: 'tester', label: 'People involved', group: 'Both' },
  { key: 'collaborators', label: 'Collaborators', group: 'Host' },
  { key: 'status', label: 'Pentest status', group: 'Host' },
  { key: 'dates', label: 'Test window', group: 'Host' },
  { key: 'service_desk', label: 'Service desk link', group: 'Host' },
  { key: 'environments', label: 'Environments', group: 'Sheet' },
  { key: 'hosts', label: 'Host count', group: 'Sheet' },
  { key: 'wave', label: 'Wave name', group: 'Sheet' },
  { key: 'classification', label: 'Classification watermark', group: 'Sheet' }
];

export const METRIC_FIELDS = [
  { key: 'findings', label: 'Total findings' },
  { key: 'critical', label: 'Critical count' },
  { key: 'high', label: 'High count' },
  { key: 'open_like', label: 'Open-like occurrences' },
  { key: 'fixed', label: 'Fixed occurrences' },
  { key: 'hosts', label: 'Host count' },
  { key: 'ports', label: 'Open ports (host only)' },
  { key: 'checklist', label: 'Checklist coverage' }
];

export const REPORT_BLOCK_LIBRARY = [
  { type: 'cover', label: 'Cover Page', description: 'Title page with optional logo.' },
  { type: 'engagement_overview', label: 'Engagement Overview', description: 'Scope, people involved, and wave.' },
  { type: 'key_metrics', label: 'Risk Snapshot', description: 'Occurrence-backed KPI tiles.' },
  { type: 'table_of_contents', label: 'Table of Contents', description: 'Finding titles and severity.' },
  { type: 'chart', label: 'Chart Section', description: 'Named production chart from the catalog.' },
  { type: 'open_ports', label: 'Open Ports', description: 'Host port table. Omits on app/wave exports.' },
  { type: 'markdown', label: 'Markdown Section', description: 'Renders a selected markdown field.' },
  { type: 'checklists', label: 'Checklist Coverage', description: 'Checklist progress. Omits when empty.' },
  { type: 'vulnerabilities', label: 'Detailed Findings', description: 'Findings with occurrence tables.' },
  { type: 'text', label: 'Text Summary', description: 'Free-form summary with placeholders.' },
  { type: 'page_break', label: 'Page Break', description: 'Starts the next section on a new PDF page.' }
];

export const REPORT_TEMPLATE_VARIABLE_GROUPS = [
  {
    key: 'scope',
    label: 'Scope',
    variables: [
      { token: '{{application.name}}', label: 'Application Name' },
      { token: '{{scope}}', label: 'Export Scope' },
      { token: '{{wave.name}}', label: 'Wave Name' },
      { token: '{{export.watermark}}', label: 'Classification' },
      { token: '{{generated_at}}', label: 'Generated Date' }
    ]
  },
  {
    key: 'record',
    label: 'Host',
    variables: [
      { token: '{{record.name}}', label: 'Target Name' },
      { token: '{{record.ip_address}}', label: 'Target IP' },
      { token: '{{record.source}}', label: 'Asset Source' },
      { token: '{{record.application_name}}', label: 'Application Name' }
    ]
  },
  {
    key: 'pentest',
    label: 'Pentest',
    variables: [
      { token: '{{pentest.status}}', label: 'Test Status' },
      { token: '{{pentest.tested_by}}', label: 'Assigned Tester' },
      { token: '{{pentest.test_start_date}}', label: 'Start Date' },
      { token: '{{pentest.test_end_date}}', label: 'End Date' },
      { token: '{{pentest.open_ports}}', label: 'Open Ports' },
      { token: '{{pentest.service_desk_link}}', label: 'Service Desk Link' }
    ]
  },
  {
    key: 'metrics',
    label: 'Metrics',
    variables: [
      { token: '{{metrics.vulnerability_count}}', label: 'Total Findings' },
      { token: '{{metrics.critical_count}}', label: 'Critical Count' },
      { token: '{{metrics.high_count}}', label: 'High Count' },
      { token: '{{metrics.critical_high_count}}', label: 'Critical + High' },
      { token: '{{metrics.open_like_count}}', label: 'Open-like Occurrences' },
      { token: '{{metrics.occurrence_fixed}}', label: 'Fixed Occurrences' },
      { token: '{{metrics.host_count}}', label: 'Host Count' },
      { token: '{{metrics.checklist_percentage}}', label: 'Checklist Completion %' }
    ]
  },
  {
    key: 'placeholders',
    label: 'Template Placeholders',
    variables: [
      { token: '{{report_title}}', label: 'Report Title' },
      { token: '{{report_subtitle}}', label: 'Report Subtitle' },
      { token: '{{prepared_by}}', label: 'Prepared By' },
      { token: '{{prepared_for}}', label: 'Prepared For' }
    ]
  }
];

const DEFAULT_BRANDING = {
  company_name: 'Security Operations',
  primary_color: '#067A8A',
  accent_color: '#1E293B',
  logo_asset_id: null,
  logo_url: '',
  header_text: '',
  footer_text: '',
  classification: ''
};

const DEFAULT_PLACEHOLDERS = {
  report_title: 'Penetration Testing Report',
  report_subtitle: 'Assessment and remediation overview',
  prepared_by: '{{pentest.tested_by}}',
  prepared_for: '{{application.name}}'
};

const DEFAULT_BLOCK_BLUEPRINTS = [
  { type: 'cover', title: '{{report_title}}', subtitle: '{{report_subtitle}}', show_logo: true },
  { type: 'engagement_overview', title: 'Engagement Overview' },
  { type: 'key_metrics', title: 'Risk Snapshot' },
  { type: 'chart', title: 'Vulnerability Severity', chart: 'vulnerability_severity' },
  { type: 'chart', title: 'Occurrence Status', chart: 'occurrence_status' },
  { type: 'vulnerabilities', title: 'Detailed Findings', include_descriptions: true },
  {
    type: 'text',
    title: 'Management Summary',
    content: 'Findings: {{metrics.vulnerability_count}}. Critical/High: {{metrics.critical_high_count}}.'
  }
];

const createUiId = () => `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;

const ensureColor = (value, fallback) => {
  const color = `${value || ''}`.trim();
  return /^#[0-9a-fA-F]{6}$/.test(color) ? color : fallback;
};

const normalizePositiveIntOrNull = (value) => {
  const numeric = Number(value);
  if (!Number.isInteger(numeric) || numeric <= 0) {
    return null;
  }
  return numeric;
};

const pickBlockBlueprint = (type) =>
  DEFAULT_BLOCK_BLUEPRINTS.find((block) => block.type === type) || {
    type: 'text',
    title: 'Custom Section',
    content: 'Add your section content here.'
  };

export const createBlockByType = (type) => ({
  _uiId: createUiId(),
  ...pickBlockBlueprint(type)
});

const normalizeBlock = (rawBlock) => {
  const input = rawBlock && typeof rawBlock === 'object' ? rawBlock : {};
  const normalizedType = `${input.type || 'text'}`.trim().toLowerCase();
  const base = pickBlockBlueprint(normalizedType);
  const { layout: _layout, _libraryItemKey: _library, ...rest } = input;
  return {
    ...base,
    ...rest,
    type: normalizedType || 'text',
    _uiId: input._uiId || createUiId()
  };
};

export const normalizeTemplateDefinition = (rawDefinition) => {
  const definition =
    rawDefinition && typeof rawDefinition === 'object' && !Array.isArray(rawDefinition)
      ? rawDefinition
      : {};

  const brandingInput = definition.branding || {};
  const placeholdersInput = definition.placeholders || {};
  const rawBlocks = Array.isArray(definition.blocks) ? definition.blocks : [];
  const blocks = (rawBlocks.length > 0 ? rawBlocks : DEFAULT_BLOCK_BLUEPRINTS).map((block) =>
    normalizeBlock(block)
  );
  const supportedScopes = Array.isArray(definition.supported_scopes)
    ? definition.supported_scopes.filter((item) =>
        ['host', 'environment', 'application', 'wave'].includes(String(item))
      )
    : [];

  return {
    version: Number.isInteger(definition.version) ? definition.version : 1,
    branding: {
      company_name: `${brandingInput.company_name || DEFAULT_BRANDING.company_name}`,
      primary_color: ensureColor(brandingInput.primary_color, DEFAULT_BRANDING.primary_color),
      accent_color: ensureColor(brandingInput.accent_color, DEFAULT_BRANDING.accent_color),
      logo_asset_id: normalizePositiveIntOrNull(brandingInput.logo_asset_id),
      logo_url: `${brandingInput.logo_url || ''}`,
      header_text: `${brandingInput.header_text || ''}`,
      footer_text: `${brandingInput.footer_text || ''}`,
      classification: `${brandingInput.classification || ''}`
    },
    placeholders: {
      report_title: `${placeholdersInput.report_title || DEFAULT_PLACEHOLDERS.report_title}`,
      report_subtitle: `${placeholdersInput.report_subtitle || DEFAULT_PLACEHOLDERS.report_subtitle}`,
      prepared_by: `${placeholdersInput.prepared_by || DEFAULT_PLACEHOLDERS.prepared_by}`,
      prepared_for: `${placeholdersInput.prepared_for || DEFAULT_PLACEHOLDERS.prepared_for}`
    },
    supported_scopes: supportedScopes,
    blocks
  };
};

export const createEmptyReportTemplateForm = () => {
  const definition = normalizeTemplateDefinition({});
  return {
    key: '',
    name: '',
    description: '',
    enabled: true,
    version: definition.version,
    branding: definition.branding,
    placeholders: definition.placeholders,
    supported_scopes: definition.supported_scopes,
    blocks: definition.blocks
  };
};

export const createReportTemplateFormFromApi = (template) => {
  const definition = normalizeTemplateDefinition(template?.template || {});
  return {
    key: template?.key || '',
    name: template?.name || '',
    description: template?.description || '',
    enabled: Boolean(template?.enabled),
    version: definition.version,
    branding: definition.branding,
    placeholders: definition.placeholders,
    supported_scopes: definition.supported_scopes,
    blocks: definition.blocks
  };
};

export const toReportTemplateDefinition = (form) => {
  const normalized = normalizeTemplateDefinition({
    version: form?.version,
    branding: form?.branding,
    placeholders: form?.placeholders,
    supported_scopes: form?.supported_scopes,
    blocks: form?.blocks
  });

  const payload = {
    version: normalized.version,
    branding: normalized.branding,
    placeholders: normalized.placeholders,
    blocks: normalized.blocks.map(({ _uiId, layout, _libraryItemKey, ...block }) => ({ ...block }))
  };
  if (normalized.supported_scopes?.length) {
    payload.supported_scopes = normalized.supported_scopes;
  }
  return payload;
};

export const getBlockLabel = (type) =>
  REPORT_BLOCK_LIBRARY.find((item) => item.type === type)?.label || 'Custom Block';
