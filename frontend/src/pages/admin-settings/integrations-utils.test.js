import {
  allowsNarrativeCombine,
  joinRaptorFields,
  kindHasReadyTemplate,
  narrativeFieldOptions,
  optionHasChoices,
  parseRaptorFields,
  raptorFieldOptions
} from './integrations-utils';

test('kindHasReadyTemplate requires a connected template', () => {
  const ready = {
    connections: [
      { kind: 'jira', templates: [{ id: 1, name: 'SEC / Bug' }] },
      { kind: 'defectdojo', templates: [] }
    ]
  };
  expect(kindHasReadyTemplate(ready, 'jira')).toBe(true);
  expect(kindHasReadyTemplate(ready, 'defectdojo')).toBe(false);
  expect(kindHasReadyTemplate({ connections: [] }, 'jira')).toBe(false);
});

test('raptor field options include a blank choice', () => {
  const options = raptorFieldOptions([{ id: 'title', label: 'Title' }]);
  expect(options[0]).toEqual({ value: '', label: 'Choose a RAPTOR field' });
  expect(options[1]).toEqual({ value: 'title', label: 'Title' });
});

test('option fields become dropdowns in the wizard', () => {
  expect(optionHasChoices('option')).toBe(true);
  expect(optionHasChoices('priority')).toBe(true);
  expect(optionHasChoices('multioption')).toBe(true);
  expect(optionHasChoices('string')).toBe(false);
});

test('narrative combine is jira description and preserves section order', () => {
  expect(allowsNarrativeCombine({ external_field_id: 'description', external_field_type: 'doc' }, 'jira')).toBe(true);
  expect(allowsNarrativeCombine({ external_field_id: 'summary', external_field_type: 'string' }, 'jira')).toBe(false);
  expect(allowsNarrativeCombine({ external_field_id: 'description', external_field_type: 'doc' }, 'defectdojo')).toBe(false);
  expect(joinRaptorFields(['evidence', 'description', 'impact'])).toBe('description,impact,evidence');
  expect(parseRaptorFields('description,impact')).toEqual(['description', 'impact']);
  expect(narrativeFieldOptions([{ id: 'impact', label: 'Impact' }])[1]).toEqual({ value: 'impact', label: 'Impact' });
});

test('admin field mapping editor can combine write-up sections into jira description', () => {
  const fs = require('fs');
  const path = require('path');
  const source = fs.readFileSync(path.join(__dirname, 'components/integrations/FieldMappingEditor.js'), 'utf8');
  expect(source).toContain('allowsNarrativeCombine');
  expect(source).toContain('Include in this field');
  expect(source).toContain('multiple');
});

test('admin integrations section maps fields instead of posting raw tickets', () => {
  const fs = require('fs');
  const path = require('path');
  const source = fs.readFileSync(path.join(__dirname, 'components/IntegrationsSection.js'), 'utf8');
  expect(source).toContain('FieldMappingEditor');
  expect(source).toContain('/api/integrations');
  expect(source).toContain('defectdojo');
  expect(source).toContain('FORM_GRID');
  expect(source).toContain('auto-fill');
  expect(source).toContain('Select a project');
  expect(source).not.toContain("gridTemplateColumns: 'minmax(180px, 280px) auto'");
  expect(source).not.toContain('auto-fit');
  expect(source).not.toContain('<Select');
  expect(source).not.toContain('<TextField');
});
