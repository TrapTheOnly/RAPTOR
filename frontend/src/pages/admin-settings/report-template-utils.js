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
  { type: 'key_metrics', label: 'Key Metrics', description: 'Executive KPI table for risk and progress.' },
  { type: 'chart', label: 'Chart', description: 'Visual trend or distribution chart.' },
  { type: 'open_ports', label: 'Open Ports', description: 'Port table with likely service mapping.' },
  { type: 'markdown', label: 'Markdown Content', description: 'Renders selected markdown content field.' },
  { type: 'checklists', label: 'Checklist Coverage', description: 'Checklist progress and completion rates.' },
  { type: 'vulnerabilities', label: 'Findings Details', description: 'Detailed vulnerabilities and CVSS data.' },
  { type: 'text', label: 'Text Summary', description: 'Free-form summary with placeholders.' },
  { type: 'page_break', label: 'Page Break', description: 'Starts the next section on a new PDF page.' }
];

const DEFAULT_BRANDING = {
  company_name: 'Security Operations',
  primary_color: '#0B5CAD',
  accent_color: '#1E293B',
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

export const createBlockByType = (type) => ({
  _uiId: createUiId(),
  ...pickBlockBlueprint(type)
});

const normalizeBlock = (rawBlock) => {
  const input = rawBlock && typeof rawBlock === 'object' ? rawBlock : {};
  const normalizedType = `${input.type || 'text'}`.trim().toLowerCase();
  const base = pickBlockBlueprint(normalizedType);
  const merged = {
    ...base,
    ...input,
    type: normalizedType || 'text',
    _uiId: input._uiId || createUiId()
  };
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
  const blocks = (rawBlocks.length > 0 ? rawBlocks : DEFAULT_BLOCK_BLUEPRINTS).map(normalizeBlock);

  return {
    version: Number.isInteger(definition.version) ? definition.version : 1,
    branding: {
      company_name: `${brandingInput.company_name || DEFAULT_BRANDING.company_name}`,
      primary_color: ensureColor(brandingInput.primary_color, DEFAULT_BRANDING.primary_color),
      accent_color: ensureColor(brandingInput.accent_color, DEFAULT_BRANDING.accent_color),
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
