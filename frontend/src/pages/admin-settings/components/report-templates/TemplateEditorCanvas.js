import React from 'react';
import {
  Button,
  Combo,
  DataList,
  DataRow,
  SwitchRow,
  Tag,
  Text
} from '../../../../design/primitives';
import { SPACE } from '../../../../design/tokens';
import ReportTemplatePaperPreview from './ReportTemplatePaperPreview';
import { PREVIEW_SCOPE_OPTIONS } from '../../report-preview-sample';
import {
  getBlockLabel,
  METRIC_FIELDS,
  OVERVIEW_FIELDS,
  REPORT_BLOCK_LIBRARY,
  REPORT_CHART_OPTIONS,
  REPORT_MARKDOWN_FIELD_OPTIONS
} from '../../report-template-utils';

const rowTitle = (label, hint) => (
  <>
    <Text as="div" variant="bodyStrong">
      {label}
    </Text>
    {hint ? (
      <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 2 }}>
        {hint}
      </Text>
    ) : null}
  </>
);

const toggleListValue = (current, allKeys, key) => {
  const active = Array.isArray(current) && current.length ? current : allKeys;
  return active.includes(key) ? active.filter((item) => item !== key) : [...active, key];
};

const TemplateEditorCanvas = ({
  blocks,
  selectedBlockId,
  selectedBlock,
  coverCount,
  previewKind,
  brandKit,
  templateForm,
  TokenField,
  onFocusField,
  onAddBlock,
  onMoveBlock,
  onRemoveBlock,
  onSelectBlock,
  onPreviewKindChange,
  onUpdateSelectedBlock
}) => (
  <div
    style={{
      display: 'grid',
      gridTemplateColumns: 'minmax(180px, 220px) minmax(0, 1fr) minmax(240px, 300px)',
      gap: SPACE.x16,
      alignItems: 'start'
    }}
  >
    <div>
      <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
        Library
      </Text>
      <DataList>
        {REPORT_BLOCK_LIBRARY.map((item) => {
          const disabled = item.type === 'cover' && coverCount >= 1;
          return (
            <DataRow
              key={item.type}
              title={rowTitle(item.label, item.description)}
              onToggle={disabled ? undefined : () => onAddBlock(item.type)}
              trailing={disabled ? <Tag>Cover in use</Tag> : null}
            />
          );
        })}
      </DataList>
    </div>

    <div>
      <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
        Flow
      </Text>
      <DataList>
        {blocks.map((block, index) => (
          <DataRow
            key={block._uiId || index}
            selected={block._uiId === selectedBlockId}
            title={rowTitle(getBlockLabel(block.type), block.title || block.chart || block.field || '')}
            onToggle={() => onSelectBlock(block._uiId)}
            trailing={
              <span style={{ display: 'flex', gap: 4 }} onClick={(event) => event.stopPropagation()}>
                <Button size="small" onClick={() => onMoveBlock(index, -1)} disabled={index === 0}>
                  Up
                </Button>
                <Button size="small" onClick={() => onMoveBlock(index, 1)} disabled={index === blocks.length - 1}>
                  Down
                </Button>
                <Button size="small" onClick={() => onRemoveBlock(index)}>
                  Remove
                </Button>
              </span>
            }
          />
        ))}
      </DataList>

      {selectedBlock ? (
        <div style={{ marginTop: SPACE.x16, display: 'flex', flexDirection: 'column', gap: SPACE.x12 }}>
          <Text as="div" variant="micro" tone="tertiary">
            Block
          </Text>
          {selectedBlock.type !== 'page_break' ? (
            <TokenField
              label="Title"
              fieldId={`block.${selectedBlock._uiId}.title`}
              value={selectedBlock.title}
              onChange={(value) => onUpdateSelectedBlock({ title: value })}
              onFocusField={onFocusField}
            />
          ) : (
            <Text variant="meta" tone="secondary">
              Page break has no editable fields.
            </Text>
          )}
          {selectedBlock.type === 'cover' ? (
            <>
              <TokenField
                label="Subtitle"
                fieldId={`block.${selectedBlock._uiId}.subtitle`}
                value={selectedBlock.subtitle}
                onChange={(value) => onUpdateSelectedBlock({ subtitle: value })}
                onFocusField={onFocusField}
              />
              <SwitchRow
                label="Show logo"
                checked={Boolean(selectedBlock.show_logo)}
                onChange={(checked) => onUpdateSelectedBlock({ show_logo: checked })}
              />
            </>
          ) : null}
          {selectedBlock.type === 'chart' ? (
            <Combo
              label="Chart"
              mode="enum"
              disableClearable
              options={REPORT_CHART_OPTIONS}
              value={selectedBlock.chart || 'vulnerability_severity'}
              onChange={(value) => onUpdateSelectedBlock({ chart: value })}
            />
          ) : null}
          {selectedBlock.type === 'markdown' ? (
            <Combo
              label="Field"
              mode="enum"
              options={REPORT_MARKDOWN_FIELD_OPTIONS}
              value={selectedBlock.field || 'description'}
              onChange={(value) => onUpdateSelectedBlock({ field: value })}
            />
          ) : null}
          {selectedBlock.type === 'text' ? (
            <TokenField
              label="Content"
              fieldId={`block.${selectedBlock._uiId}.content`}
              value={selectedBlock.content}
              multiline
              rows={6}
              onChange={(value) => onUpdateSelectedBlock({ content: value })}
              onFocusField={onFocusField}
            />
          ) : null}
          {selectedBlock.type === 'vulnerabilities' ? (
            <SwitchRow
              label="Include descriptions"
              checked={Boolean(selectedBlock.include_descriptions)}
              onChange={(checked) => onUpdateSelectedBlock({ include_descriptions: checked })}
            />
          ) : null}
          {selectedBlock.type === 'engagement_overview' ? (
            <div>
              <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
                Rows on this block
              </Text>
              {['Host', 'Both', 'Sheet'].map((group) => (
                <div key={group} style={{ marginBottom: SPACE.x8 }}>
                  <Text as="div" variant="meta" tone="secondary" style={{ marginBottom: 4 }}>
                    {group === 'Both' ? 'Host and sheet' : group}
                  </Text>
                  {OVERVIEW_FIELDS.filter((item) => item.group === group).map((item) => {
                    const active = !selectedBlock.fields?.length || selectedBlock.fields.includes(item.key);
                    return (
                      <SwitchRow
                        key={item.key}
                        label={item.label}
                        checked={active}
                        onChange={() =>
                          onUpdateSelectedBlock({
                            fields: toggleListValue(
                              selectedBlock.fields,
                              OVERVIEW_FIELDS.map((entry) => entry.key),
                              item.key
                            )
                          })
                        }
                      />
                    );
                  })}
                </div>
              ))}
            </div>
          ) : null}
          {selectedBlock.type === 'key_metrics' ? (
            <div>
              <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
                Tiles on this block
              </Text>
              {METRIC_FIELDS.map((item) => {
                const active = !selectedBlock.fields?.length || selectedBlock.fields.includes(item.key);
                return (
                  <SwitchRow
                    key={item.key}
                    label={item.label}
                    checked={active}
                    onChange={() =>
                      onUpdateSelectedBlock({
                        fields: toggleListValue(
                          selectedBlock.fields,
                          METRIC_FIELDS.map((entry) => entry.key),
                          item.key
                        )
                      })
                    }
                  />
                );
              })}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>

    <div>
      <Combo
        label="Preview envelope"
        mode="enum"
        disableClearable
        options={PREVIEW_SCOPE_OPTIONS}
        value={previewKind}
        onChange={onPreviewKindChange}
      />
      <div style={{ marginTop: SPACE.x12 }}>
        <ReportTemplatePaperPreview templateForm={templateForm} previewKind={previewKind} brandKit={brandKit} />
      </div>
    </div>
  </div>
);

export default TemplateEditorCanvas;
