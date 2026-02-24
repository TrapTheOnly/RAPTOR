export const REPORT_CHART_OPTIONS = [
  {
    value: 'vulnerability_severity',
    label: 'Vulnerability Severity Distribution'
  },
  {
    value: 'checklist_completion',
    label: 'Checklist Completion Status'
  },
  {
    value: 'vulnerability_fix_status',
    label: 'Open vs Remediated Findings'
  }
];

export const REPORT_MARKDOWN_FIELD_OPTIONS = [
  { value: 'description', label: 'Asset Description' },
  { value: 'notes', label: 'Security Details' },
  { value: 'open_ports', label: 'Open Ports Text' }
];

export const REPORT_BLOCK_LIBRARY = [
  { type: 'cover', label: 'Cover Page', description: 'Hero section with title, subtitle, and optional logo.' },
  { type: 'engagement_overview', label: 'Engagement Overview', description: 'Target details, tester, dates, and status.' },
  { type: 'key_metrics', label: 'Risk Snapshot', description: 'Executive KPI table for risk and progress.' },
  { type: 'chart', label: 'Chart Section', description: 'Visual trend or distribution chart.' },
  { type: 'open_ports', label: 'Open Ports', description: 'Port table with likely service mapping.' },
  { type: 'markdown', label: 'Markdown Section', description: 'Renders selected markdown content field.' },
  { type: 'checklists', label: 'Checklist Coverage', description: 'Checklist progress and completion rates.' },
  { type: 'vulnerabilities', label: 'Detailed Findings', description: 'Detailed vulnerabilities and CVSS data.' },
  { type: 'text', label: 'Text Summary', description: 'Free-form summary with placeholders.' },
  { type: 'page_break', label: 'Page Break', description: 'Starts the next section on a new PDF page.' }
];

export const REPORT_TEMPLATE_VARIABLE_GROUPS = [
  {
    key: 'record',
    label: 'Record',
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
      { token: '{{pentest.service_desk_link}}', label: 'Service Desk Link' },
      { token: '{{pentest.vulnerable}}', label: 'Vulnerable Flag' },
      { token: '{{pentest.vulnerability_fixed}}', label: 'Remediated Flag' },
      { token: '{{generated_at}}', label: 'Generated Time' }
    ]
  },
  {
    key: 'metrics',
    label: 'Metrics',
    variables: [
      { token: '{{metrics.vulnerability_count}}', label: 'Total Findings' },
      { token: '{{metrics.critical_count}}', label: 'Critical Count' },
      { token: '{{metrics.high_count}}', label: 'High Count' },
      { token: '{{metrics.medium_count}}', label: 'Medium Count' },
      { token: '{{metrics.low_count}}', label: 'Low Count' },
      { token: '{{metrics.critical_high_count}}', label: 'Critical + High' },
      { token: '{{metrics.open_findings}}', label: 'Open Findings' },
      { token: '{{metrics.fixed_findings}}', label: 'Fixed Findings' },
      { token: '{{metrics.open_ports_count}}', label: 'Open Port Count' },
      { token: '{{metrics.checklist_total}}', label: 'Checklist Total' },
      { token: '{{metrics.checklist_completed}}', label: 'Checklist Completed' },
      { token: '{{metrics.checklist_irrelevant}}', label: 'Checklist Irrelevant' },
      { token: '{{metrics.checklist_unstarted}}', label: 'Checklist Unstarted' },
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
  primary_color: '#0B5CAD',
  accent_color: '#1E293B',
  logo_asset_id: null,
  logo_url: ''
};

const DEFAULT_PLACEHOLDERS = {
  report_title: 'Penetration Testing Report',
  report_subtitle: 'Comprehensive assessment and remediation overview',
  prepared_by: '{{pentest.tested_by}}',
  prepared_for: '{{record.name}}'
};

const DEFAULT_BLOCK_BLUEPRINTS = [
  { type: 'cover', title: '{{report_title}}', subtitle: '{{report_subtitle}}', show_logo: true },
  { type: 'engagement_overview', title: 'Engagement Overview' },
  { type: 'key_metrics', title: 'Risk Snapshot' },
  { type: 'chart', title: 'Vulnerability Severity Distribution', chart: 'vulnerability_severity' },
  { type: 'chart', title: 'Checklist Completion Status', chart: 'checklist_completion' },
  { type: 'chart', title: 'Open vs Remediated Findings', chart: 'vulnerability_fix_status' },
  { type: 'open_ports', title: 'Open Ports' },
  { type: 'markdown', title: 'Asset Description', field: 'description' },
  { type: 'markdown', title: 'Security Details', field: 'notes' },
  { type: 'checklists', title: 'Checklist Coverage' },
  { type: 'vulnerabilities', title: 'Detailed Findings', include_descriptions: true },
  {
    type: 'text',
    title: 'Management Summary',
    content:
      'Findings detected: {{metrics.vulnerability_count}}. Critical/High findings: {{metrics.critical_high_count}}.'
  }
];

const createUiId = () => `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;

const DEFAULT_BLOCK_LAYOUT = {
  cover: { w: 12, h: 5 },
  engagement_overview: { w: 6, h: 4 },
  key_metrics: { w: 6, h: 4 },
  chart: { w: 6, h: 5 },
  open_ports: { w: 6, h: 4 },
  markdown: { w: 6, h: 5 },
  checklists: { w: 6, h: 5 },
  vulnerabilities: { w: 8, h: 7 },
  text: { w: 6, h: 4 },
  page_break: { w: 12, h: 2 }
};

const ensureColor = (value, fallback) => {
  const color = `${value || ''}`.trim();
  return /^#[0-9a-fA-F]{6}$/.test(color) ? color : fallback;
};

const pickBlockBlueprint = (type) =>
  DEFAULT_BLOCK_BLUEPRINTS.find((block) => block.type === type) || {
    type: 'text',
    title: 'Custom Section',
    content: 'Add your section content here.'
  };

const normalizeInt = (value, fallback) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.round(numeric) : fallback;
};

const normalizePositiveIntOrNull = (value) => {
  const numeric = Number(value);
  if (!Number.isInteger(numeric) || numeric <= 0) {
    return null;
  }
  return numeric;
};

const normalizeLayout = (layout, type, index) => {
  const baseLayout = DEFAULT_BLOCK_LAYOUT[type] || DEFAULT_BLOCK_LAYOUT.text;
  const raw = layout && typeof layout === 'object' ? layout : {};
  return {
    x: Math.max(0, normalizeInt(raw.x, (index % 2) * 6)),
    y: Math.max(0, normalizeInt(raw.y, Math.floor(index / 2) * 4)),
    w: Math.min(12, Math.max(2, normalizeInt(raw.w, baseLayout.w))),
    h: Math.min(20, Math.max(2, normalizeInt(raw.h, baseLayout.h)))
  };
};

export const createBlockByType = (type, index = 0) => ({
  _uiId: createUiId(),
  ...pickBlockBlueprint(type),
  layout: normalizeLayout({}, type, index)
});

const normalizeBlock = (rawBlock, index) => {
  const input = rawBlock && typeof rawBlock === 'object' ? rawBlock : {};
  const normalizedType = `${input.type || 'text'}`.trim().toLowerCase();
  const base = pickBlockBlueprint(normalizedType);
  const merged = {
    ...base,
    ...input,
    type: normalizedType || 'text',
    _uiId: input._uiId || createUiId()
  };
  merged.layout = normalizeLayout(input.layout, merged.type, index);
  return merged;
};

export const normalizeTemplateDefinition = (rawDefinition) => {
  const definition =
    rawDefinition && typeof rawDefinition === 'object' && !Array.isArray(rawDefinition)
      ? rawDefinition
      : {};

  const brandingInput = definition.branding || {};
  const placeholdersInput = definition.placeholders || {};
  const rawBlocks = Array.isArray(definition.blocks) ? definition.blocks : [];
  const blocks = (rawBlocks.length > 0 ? rawBlocks : DEFAULT_BLOCK_BLUEPRINTS).map((block, index) =>
    normalizeBlock(block, index)
  );

  return {
    version: Number.isInteger(definition.version) ? definition.version : 1,
    branding: {
      company_name: `${brandingInput.company_name || DEFAULT_BRANDING.company_name}`,
      primary_color: ensureColor(brandingInput.primary_color, DEFAULT_BRANDING.primary_color),
      accent_color: ensureColor(brandingInput.accent_color, DEFAULT_BRANDING.accent_color),
      logo_asset_id: normalizePositiveIntOrNull(brandingInput.logo_asset_id),
      logo_url: `${brandingInput.logo_url || ''}`
    },
    placeholders: {
      report_title: `${placeholdersInput.report_title || DEFAULT_PLACEHOLDERS.report_title}`,
      report_subtitle: `${placeholdersInput.report_subtitle || DEFAULT_PLACEHOLDERS.report_subtitle}`,
      prepared_by: `${placeholdersInput.prepared_by || DEFAULT_PLACEHOLDERS.prepared_by}`,
      prepared_for: `${placeholdersInput.prepared_for || DEFAULT_PLACEHOLDERS.prepared_for}`
    },
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
    blocks: definition.blocks
  };
};

export const toReportTemplateDefinition = (form) => {
  const normalized = normalizeTemplateDefinition({
    version: form?.version,
    branding: form?.branding,
    placeholders: form?.placeholders,
    blocks: form?.blocks
  });

  return {
    version: normalized.version,
    branding: normalized.branding,
    placeholders: normalized.placeholders,
    blocks: normalized.blocks.map(({ _uiId, ...block }) => ({ ...block }))
  };
};

export const getBlockLabel = (type) =>
  REPORT_BLOCK_LIBRARY.find((item) => item.type === type)?.label || 'Custom Block';
