import React from 'react';
import { Button, Combo, Field, Surface, Tag, Text } from '../../../../design/primitives';
import { SPACE } from '../../../../design/tokens';
import {
  FILL_MODES,
  NARRATIVE_FIELD_IDS,
  allowsNarrativeCombine,
  joinRaptorFields,
  narrativeFieldOptions,
  optionHasChoices,
  parseRaptorFields,
  raptorFieldOptions
} from '../../integrations-utils';

const FieldMappingEditor = ({
  mappings = [],
  raptorFields = [],
  kind = 'jira',
  onChange,
  onRefresh,
  refreshing = false,
  saving = false,
  onSave
}) => {
  const update = (index, patch) => {
    onChange(mappings.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <Text as="p" variant="meta" tone="secondary" style={{ margin: 0, maxWidth: 560 }}>
          RAPTOR fills what it can from the finding. Jira Description can combine Description, Impact,
          Evidence, and Remediation into one write-up. Other fields map one-to-one. Everything marked
          “Ask when sending” becomes a control in the send wizard.
        </Text>
        <div style={{ display: 'flex', gap: 8 }}>
          {onRefresh ? (
            <Button size="small" onClick={onRefresh} disabled={refreshing}>
              {refreshing ? 'Refreshing…' : 'Refresh fields'}
            </Button>
          ) : null}
          {onSave ? (
            <Button size="small" variant="contained" onClick={onSave} disabled={saving}>
              {saving ? 'Saving…' : 'Save mapping'}
            </Button>
          ) : null}
        </div>
      </div>

      {mappings.length === 0 ? (
        <Text variant="meta" tone="secondary">
          Load a project and issue type to see its fields.
        </Text>
      ) : (
        mappings.map((mapping, index) => (
          <Surface key={mapping.external_field_id || index} style={{ padding: SPACE.x16 }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'minmax(160px, 1fr) minmax(160px, 200px) minmax(180px, 1fr)',
                gap: SPACE.x12,
                alignItems: 'start'
              }}
            >
              <div>
                <Text as="div" variant="bodyStrong">
                  {mapping.external_field_name || mapping.external_field_id}
                </Text>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                  {mapping.required ? <Tag emphasized>required</Tag> : <Tag>optional</Tag>}
                  {mapping.external_field_id?.startsWith?.('customfield_') ? <Tag>custom</Tag> : null}
                  {optionHasChoices(mapping.external_field_type) ? (
                    <Tag>{`${(mapping.allowed_values || []).length} choices`}</Tag>
                  ) : null}
                </div>
              </div>
              <Combo
                label="Fill"
                options={FILL_MODES}
                value={mapping.fill_mode || 'ask'}
                onChange={(value) =>
                  update(index, {
                    fill_mode: value,
                    raptor_field:
                      value === 'mapped'
                        ? mapping.raptor_field ||
                          (allowsNarrativeCombine(mapping, kind) ? NARRATIVE_FIELD_IDS.join(',') : '')
                        : ''
                  })
                }
              />
              {mapping.fill_mode === 'mapped' && allowsNarrativeCombine(mapping, kind) ? (
                <Combo
                  label="Include in this field"
                  multiple
                  placeholder="Choose RAPTOR sections"
                  hint="Empty sections are omitted. Order is Description, Impact, Evidence, Remediation."
                  options={narrativeFieldOptions(raptorFields)}
                  filterSelectedOptions={false}
                  value={
                    parseRaptorFields(mapping.raptor_field).length
                      ? parseRaptorFields(mapping.raptor_field)
                      : NARRATIVE_FIELD_IDS
                  }
                  onChange={(value) => update(index, { raptor_field: joinRaptorFields(value) })}
                />
              ) : null}
              {mapping.fill_mode === 'mapped' && !allowsNarrativeCombine(mapping, kind) ? (
                <Combo
                  label="RAPTOR field"
                  options={raptorFieldOptions(raptorFields)}
                  value={mapping.raptor_field || ''}
                  onChange={(value) => update(index, { raptor_field: value })}
                />
              ) : null}
              {mapping.fill_mode === 'static' ? (
                optionHasChoices(mapping.external_field_type) ? (
                  <Combo
                    label="Fixed value"
                    options={(mapping.allowed_values || []).map((option) => ({
                      value: option.id || option.value,
                      label: option.label || option.value
                    }))}
                    value={mapping.static_value || ''}
                    onChange={(value) => update(index, { static_value: value })}
                  />
                ) : (
                  <Field
                    label="Fixed value"
                    value={mapping.static_value || ''}
                    onChange={(event) => update(index, { static_value: event.target.value })}
                  />
                )
              ) : null}
              {mapping.fill_mode === 'ask' ? (
                <Text variant="meta" tone="secondary" style={{ paddingTop: 22 }}>
                  {optionHasChoices(mapping.external_field_type)
                    ? 'Shown as a dropdown in the send wizard.'
                    : 'Shown as a field in the send wizard.'}
                </Text>
              ) : null}
              {mapping.fill_mode === 'skip' ? (
                <Text variant="meta" tone="secondary" style={{ paddingTop: 22 }}>
                  Not sent.
                </Text>
              ) : null}
            </div>
          </Surface>
        ))
      )}
    </div>
  );
};

export default FieldMappingEditor;
