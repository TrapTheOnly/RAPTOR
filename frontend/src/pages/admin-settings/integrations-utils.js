export const KIND_META = {
  jira: {
    label: 'Jira',
    connectHint: 'Use a Jira Cloud API token or a Data Center personal access token. RAPTOR never shows the secret again.',
    templateNoun: 'ticket template',
    projectLabel: 'Project',
    typeLabel: 'Issue type'
  },
  defectdojo: {
    label: 'DefectDojo',
    connectHint: 'Paste the DefectDojo API key from the user’s profile. RAPTOR never shows the secret again.',
    templateNoun: 'product mapping',
    projectLabel: 'Product',
    typeLabel: 'Engagement'
  }
};

export const FILL_MODES = [
  { value: 'mapped', label: 'Fill from RAPTOR' },
  { value: 'ask', label: 'Ask when sending' },
  { value: 'static', label: 'Fixed value' },
  { value: 'skip', label: 'Ignore' }
];

export const NARRATIVE_FIELD_IDS = ['description', 'impact', 'evidence', 'remediation'];

export const parseRaptorFields = (value) =>
  String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

export const joinRaptorFields = (ids = []) => {
  const wanted = new Set((ids || []).map((item) => String(item).trim()).filter(Boolean));
  return NARRATIVE_FIELD_IDS.filter((id) => wanted.has(id)).concat(
    [...wanted].filter((id) => !NARRATIVE_FIELD_IDS.includes(id))
  ).join(',');
};

export const allowsNarrativeCombine = (mapping, kind) => {
  if (kind && kind !== 'jira') return false;
  const id = String(mapping?.external_field_id || '').toLowerCase();
  const name = String(mapping?.external_field_name || '').toLowerCase();
  const type = String(mapping?.external_field_type || '').toLowerCase();
  if (id === 'summary') return false;
  if (id === 'description') return true;
  return ['text', 'doc'].includes(type) && name.includes('description');
};

export const narrativeFieldOptions = (fields = []) => {
  const byId = Object.fromEntries((fields || []).map((field) => [field.id, field.label]));
  return NARRATIVE_FIELD_IDS.map((id) => ({
    value: id,
    label: byId[id] || id.replace(/_/g, ' ').replace(/\b\w/g, (char) => char.toUpperCase())
  }));
};

export const ENGAGEMENT_MODES = [
  { value: 'per_wave', label: 'One engagement per wave' },
  { value: 'fixed', label: 'Always this engagement' },
  { value: 'ask', label: 'Ask when sending' }
];

export const TEST_MODES = [
  { value: 'create', label: 'Create a RAPTOR test if missing' },
  { value: 'fixed', label: 'Always this test' },
  { value: 'ask', label: 'Ask when sending' }
];

export const raptorFieldOptions = (fields = []) =>
  [{ value: '', label: 'Choose a RAPTOR field' }].concat(
    fields.map((field) => ({ value: field.id, label: field.label }))
  );

export const optionHasChoices = (type) =>
  ['option', 'priority', 'multioption'].includes(String(type || ''));

export const isMultiValue = (type) => ['multioption', 'labels'].includes(String(type || ''));

export const kindHasReadyTemplate = (ready, kind) =>
  (ready?.connections || []).some(
    (connection) => connection.kind === kind && (connection.templates || []).length > 0
  );
