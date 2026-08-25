import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import axios from 'axios';
import {
  Button,
  Field,
  Panel,
  SwitchRow,
  Tabs,
  Tag,
  Text,
  Toolbar
} from '../../../design/primitives';
import { SPACE, TYPE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import SectionHeader from './SectionHeader';
import TemplateEditorCanvas from './report-templates/TemplateEditorCanvas';
import VariablePicker from './report-templates/VariablePicker';
import { createBlockByType, toReportTemplateDefinition } from '../report-template-utils';

const SCOPE_OPTIONS = [
  { value: 'host', label: 'Host' },
  { value: 'environment', label: 'Environment' },
  { value: 'application', label: 'Application' },
  { value: 'wave', label: 'Wave' }
];

const PAGE_TABS = [
  { value: 'brand-kit', label: 'Brand kit' },
  { value: 'info', label: 'Template info' },
  { value: 'design', label: 'Template design' }
];

const DEFAULT_KIT = {
  company_name: 'Security Operations',
  print_ink: '#067A8A',
  logo_url: ''
};

const HEX = /^#[0-9a-fA-F]{6}$/;

const formSignature = (form) =>
  JSON.stringify({
    key: form?.key || '',
    name: form?.name || '',
    description: form?.description || '',
    enabled: Boolean(form?.enabled),
    definition: toReportTemplateDefinition(form)
  });

const TokenField = ({ label, value, fieldId, multiline = false, onChange, onFocusField, onInsertToken, rows = 3 }) => {
  const palette = usePalette();
  const inputRef = useRef(null);
  const wrapRef = useRef(null);
  const [pickerOpen, setPickerOpen] = useState(false);

  useEffect(() => {
    if (!pickerOpen) return undefined;
    const onPointerDown = (event) => {
      if (!wrapRef.current?.contains(event.target)) setPickerOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [pickerOpen]);

  return (
    <div ref={wrapRef} style={{ position: 'relative', minWidth: 0, width: '100%' }}>
      <Field
        label={label}
        value={value || ''}
        multiline={multiline}
        minRows={multiline ? rows : undefined}
        inputRef={inputRef}
        onFocus={() => onFocusField({ fieldId, inputRef })}
        onChange={(event) => onChange(event.target.value)}
        trailing={
          <button
            type="button"
            aria-label="Insert variable"
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => {
              onFocusField({ fieldId, inputRef });
              setPickerOpen((open) => !open);
            }}
            style={{
              width: 28,
              height: 28,
              marginRight: 4,
              border: 0,
              background: 'transparent',
              color: pickerOpen ? palette.accent : palette.textTertiary,
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 13,
              fontWeight: 700
            }}
          >
            {'{ }'}
          </button>
        }
      />
      <VariablePicker
        open={pickerOpen}
        onSelect={(token) => {
          onInsertToken(token, { fieldId, inputRef });
          setPickerOpen(false);
        }}
      />
    </div>
  );
};

const InkPicker = ({ value, onChange }) => {
  const palette = usePalette();
  const hex = HEX.test(value) ? value : '#067A8A';
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0, flex: 1 }}>
      <span style={{ ...TYPE.micro, color: palette.textTertiary }}>Print ink</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x12 }}>
        <input
          type="color"
          value={hex}
          aria-label="Print ink"
          onChange={(event) => onChange(event.target.value.toUpperCase())}
          style={{
            width: 32,
            height: 32,
            padding: 0,
            border: `1px solid ${palette.line}`,
            background: 'transparent',
            cursor: 'pointer'
          }}
        />
        <Field
          value={value || ''}
          onChange={(event) => onChange(event.target.value)}
          hint="Hex used on generated PDFs."
        />
      </div>
    </label>
  );
};

const BrandKitPanel = ({ showMessage, onKitChange }) => {
  const [kit, setKit] = useState(DEFAULT_KIT);
  const [saving, setSaving] = useState(false);
  const fileRef = useRef(null);

  const applyKit = (next) => {
    setKit(next);
    onKitChange?.(next);
  };

  const load = useCallback(async () => {
    try {
      const response = await axios.get('/report-brand-kit');
      if (response.data?.kit) {
        setKit(response.data.kit);
        onKitChange?.(response.data.kit);
      }
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to load brand kit.');
    }
  }, [showMessage, onKitChange]);

  useEffect(() => {
    load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const response = await axios.put('/report-brand-kit', {
        company_name: kit.company_name,
        print_ink: kit.print_ink
      });
      if (response.data?.kit) applyKit(response.data.kit);
      showMessage?.('success', 'Brand kit saved.');
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to save brand kit.');
    } finally {
      setSaving(false);
    }
  };

  const uploadLogo = async (file) => {
    if (!file) return;
    const formData = new FormData();
    formData.append('logo', file);
    try {
      const response = await axios.post('/report-brand-kit/logo-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      if (response.data?.kit) applyKit(response.data.kit);
      showMessage?.('success', 'Brand kit logo uploaded.');
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to upload logo.');
    }
  };

  return (
    <div style={{ maxWidth: 640 }}>
      <SectionHeader title="Org brand kit">
        <Button size="small" variant="contained" onClick={save} disabled={saving}>
          Save brand kit
        </Button>
      </SectionHeader>
      <Text as="p" variant="meta" tone="secondary" style={{ marginTop: 0, marginBottom: SPACE.x16 }}>
        Company name, print ink, and logo apply to every generated PDF, including new templates. Template design only
        owns chrome strings and block order.
      </Text>
      <Field
        label="Company name"
        value={kit.company_name || ''}
        onChange={(event) => setKit((prev) => ({ ...prev, company_name: event.target.value }))}
        style={{ marginBottom: SPACE.x16 }}
      />
      <div style={{ marginBottom: SPACE.x16 }}>
        <InkPicker
          value={kit.print_ink || ''}
          onChange={(print_ink) => setKit((prev) => ({ ...prev, print_ink }))}
        />
      </div>
      <div style={{ display: 'flex', gap: SPACE.x12, alignItems: 'center' }}>
        <input
          ref={fileRef}
          type="file"
          accept="image/png"
          style={{ display: 'none' }}
          onChange={(event) => {
            uploadLogo(event.target.files?.[0]);
            event.target.value = '';
          }}
        />
        <Button size="small" onClick={() => fileRef.current?.click()}>
          Upload PNG logo
        </Button>
        {kit.logo_url ? (
          <img src={kit.logo_url} alt="" style={{ height: 28, objectFit: 'contain' }} />
        ) : (
          <Text variant="meta" tone="secondary">
            No logo
          </Text>
        )}
      </div>
    </div>
  );
};

const ReportTemplatesSection = ({
  selectedTemplate,
  templateForm,
  onChangeTemplateForm,
  onSaveTemplate,
  onDeleteTemplate,
  onResetTemplate,
  onDuplicateTemplate,
  showMessage
}) => {
  const [page, setPage] = useState('info');
  const [selectedBlockId, setSelectedBlockId] = useState(null);
  const [previewKind, setPreviewKind] = useState('owner_delivery');
  const [brandKit, setBrandKit] = useState(DEFAULT_KIT);
  const [editorOpen, setEditorOpen] = useState(false);
  const [discardOpen, setDiscardOpen] = useState(false);
  const [editorDirty, setEditorDirty] = useState(false);
  const [formDirty, setFormDirty] = useState(false);
  const focusedFieldRef = useRef(null);
  const editorSnapshotRef = useRef('[]');
  const formBaselineRef = useRef('');
  const lastLoadedRef = useRef(null);
  const palette = usePalette();

  useEffect(() => {
    axios
      .get('/report-brand-kit')
      .then((response) => {
        if (response.data?.kit) setBrandKit(response.data.kit);
      })
      .catch(() => {});
  }, []);

  const blocks = useMemo(
    () => (Array.isArray(templateForm?.blocks) ? templateForm.blocks : []),
    [templateForm?.blocks]
  );

  const loadedSignature = useMemo(
    () =>
      JSON.stringify({
        id: selectedTemplate?.id ?? null,
        key: selectedTemplate?.key,
        name: selectedTemplate?.name,
        description: selectedTemplate?.description,
        enabled: selectedTemplate?.enabled,
        supported_scopes: selectedTemplate?.supported_scopes,
        template: selectedTemplate?.template
      }),
    [selectedTemplate]
  );

  useEffect(() => {
    const signature = formSignature(templateForm);
    if (loadedSignature !== lastLoadedRef.current) {
      lastLoadedRef.current = loadedSignature;
      formBaselineRef.current = signature;
      setFormDirty(false);
      return;
    }
    setFormDirty(signature !== formBaselineRef.current);
  }, [templateForm, loadedSignature]);

  useEffect(() => {
    if (!blocks.length) {
      setSelectedBlockId(null);
      return;
    }
    if (!blocks.some((block) => block._uiId === selectedBlockId)) {
      setSelectedBlockId(blocks[0]._uiId);
    }
  }, [blocks, selectedBlockId]);

  useEffect(() => {
    if (!editorOpen) return;
    setEditorDirty(JSON.stringify(blocks) !== editorSnapshotRef.current);
  }, [blocks, editorOpen]);

  const selectedBlock = blocks.find((block) => block._uiId === selectedBlockId) || null;
  const coverCount = blocks.filter((block) => block.type === 'cover').length;
  const systemTemplate = Boolean(selectedTemplate?.is_system);

  const setBlocks = (next) => onChangeTemplateForm('blocks', next);
  const setBranding = (patch) =>
    onChangeTemplateForm('branding', { ...(templateForm.branding || {}), ...patch });
  const setPlaceholders = (patch) =>
    onChangeTemplateForm('placeholders', { ...(templateForm.placeholders || {}), ...patch });

  const addBlock = (type) => {
    if (type === 'cover' && coverCount >= 1) return;
    const next = createBlockByType(type);
    setBlocks([...blocks, next]);
    setSelectedBlockId(next._uiId);
  };

  const moveBlock = (index, delta) => {
    const nextIndex = index + delta;
    if (nextIndex < 0 || nextIndex >= blocks.length) return;
    const next = [...blocks];
    const [item] = next.splice(index, 1);
    next.splice(nextIndex, 0, item);
    setBlocks(next);
  };

  const removeBlock = (index) => {
    setBlocks(blocks.filter((_, itemIndex) => itemIndex !== index));
  };

  const updateSelectedBlock = (patch) => {
    setBlocks(blocks.map((block) => (block._uiId === selectedBlockId ? { ...block, ...patch } : block)));
  };

  const toggleScope = (scope) => {
    const current = Array.isArray(templateForm.supported_scopes) ? templateForm.supported_scopes : [];
    const next = current.includes(scope) ? current.filter((item) => item !== scope) : [...current, scope];
    onChangeTemplateForm('supported_scopes', next);
  };

  const readFieldValue = (fieldId) => {
    if (fieldId === 'placeholders.report_title') return templateForm.placeholders?.report_title || '';
    if (fieldId === 'placeholders.report_subtitle') return templateForm.placeholders?.report_subtitle || '';
    if (fieldId === 'placeholders.prepared_by') return templateForm.placeholders?.prepared_by || '';
    if (fieldId === 'placeholders.prepared_for') return templateForm.placeholders?.prepared_for || '';
    if (fieldId === 'branding.header_text') return templateForm.branding?.header_text || '';
    if (fieldId === 'branding.footer_text') return templateForm.branding?.footer_text || '';
    if (fieldId === 'branding.classification') return templateForm.branding?.classification || '';
    if (fieldId?.startsWith('block.')) {
      const parts = fieldId.split('.');
      const block = blocks.find((item) => item._uiId === parts[1]);
      const key = parts.slice(2).join('.');
      return (block && key && block[key]) || '';
    }
    return '';
  };

  const writeFieldValue = (fieldId, value) => {
    if (fieldId === 'placeholders.report_title') setPlaceholders({ report_title: value });
    else if (fieldId === 'placeholders.report_subtitle') setPlaceholders({ report_subtitle: value });
    else if (fieldId === 'placeholders.prepared_by') setPlaceholders({ prepared_by: value });
    else if (fieldId === 'placeholders.prepared_for') setPlaceholders({ prepared_for: value });
    else if (fieldId === 'branding.header_text') setBranding({ header_text: value });
    else if (fieldId === 'branding.footer_text') setBranding({ footer_text: value });
    else if (fieldId === 'branding.classification') setBranding({ classification: value });
    else if (fieldId?.startsWith('block.')) {
      const parts = fieldId.split('.');
      const uiId = parts[1];
      const key = parts.slice(2).join('.');
      setBlocks(blocks.map((block) => (block._uiId === uiId ? { ...block, [key]: value } : block)));
    }
  };

  const insertToken = (token, target) => {
    const focused = target || focusedFieldRef.current;
    if (!focused?.fieldId) return;
    focusedFieldRef.current = focused;
    const current = readFieldValue(focused.fieldId);
    const el = focused.inputRef?.current;
    if (el && typeof el.selectionStart === 'number') {
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const next = `${current.slice(0, start)}${token}${current.slice(end)}`;
      writeFieldValue(focused.fieldId, next);
      requestAnimationFrame(() => {
        el.focus();
        const caret = start + token.length;
        el.setSelectionRange(caret, caret);
      });
      return;
    }
    writeFieldValue(focused.fieldId, `${current}${token}`);
  };

  const insertTokenRef = useRef(() => {});
  insertTokenRef.current = insertToken;

  const BoundTokenField = useMemo(
    () =>
      function BoundTokenField(props) {
        return (
          <TokenField
            {...props}
            onInsertToken={(token, target) => insertTokenRef.current(token, target)}
          />
        );
      },
    []
  );

  const onFocusField = (payload) => {
    focusedFieldRef.current = payload;
  };

  const openEditor = () => {
    editorSnapshotRef.current = JSON.stringify(blocks);
    setEditorDirty(false);
    setDiscardOpen(false);
    setEditorOpen(true);
  };

  const closeEditor = () => {
    setDiscardOpen(false);
    setEditorOpen(false);
    setEditorDirty(false);
  };

  const requestCloseEditor = () => {
    if (discardOpen) return;
    if (editorDirty) {
      setDiscardOpen(true);
      return;
    }
    closeEditor();
  };

  const discardEditor = () => {
    try {
      const snapshot = JSON.parse(editorSnapshotRef.current);
      if (Array.isArray(snapshot)) setBlocks(snapshot);
    } catch (error) {
      /* keep current blocks if the snapshot cannot be parsed */
    }
    closeEditor();
  };

  const saveEditor = async () => {
    await onSaveTemplate?.();
    editorSnapshotRef.current = JSON.stringify(blocks);
    setEditorDirty(false);
  };

  const identityActions = (
    <Toolbar style={{ marginBottom: 0 }} nowrap>
      {systemTemplate && selectedTemplate?.is_customized ? (
        <Button size="small" onClick={() => onResetTemplate(selectedTemplate)}>
          Reset canonical
        </Button>
      ) : null}
      {selectedTemplate?.id && !systemTemplate ? (
        <Button size="small" onClick={() => onDeleteTemplate(selectedTemplate.id, selectedTemplate.name)}>
          Delete
        </Button>
      ) : null}
      <Button size="small" variant="contained" disabled={!formDirty} onClick={onSaveTemplate}>
        {formDirty ? 'Save changes' : 'Saved'}
      </Button>
    </Toolbar>
  );

  return (
    <div>
      <Tabs value={page} onChange={setPage} items={PAGE_TABS} />
      {page === 'brand-kit' ? <BrandKitPanel showMessage={showMessage} onKitChange={setBrandKit} /> : null}

      {page === 'info' ? (
        <div>
          <SectionHeader title={selectedTemplate?.name || 'New report template'}>{identityActions}</SectionHeader>
          <Toolbar>
            <Field
              label="Key"
              value={templateForm.key || ''}
              disabled={systemTemplate}
              onChange={(event) => onChangeTemplateForm('key', event.target.value)}
            />
            <Field
              label="Name"
              value={templateForm.name || ''}
              onChange={(event) => onChangeTemplateForm('name', event.target.value)}
            />
          </Toolbar>
          <Field
            label="Description"
            value={templateForm.description || ''}
            onChange={(event) => onChangeTemplateForm('description', event.target.value)}
            style={{ marginBottom: SPACE.x16 }}
          />
          <SwitchRow
            label="Enabled"
            hint="Disabled templates are hidden from standard generate lists."
            checked={Boolean(templateForm.enabled)}
            onChange={(checked) => onChangeTemplateForm('enabled', checked)}
          />
          <Text as="div" variant="micro" tone="tertiary" style={{ marginTop: SPACE.x16, marginBottom: 8 }}>
            Supported scopes
          </Text>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: SPACE.x8 }}>
            {SCOPE_OPTIONS.map((option) => {
              const active = (templateForm.supported_scopes || []).includes(option.value);
              return (
                <Tag
                  key={option.value}
                  emphasized={active}
                  onClick={() => toggleScope(option.value)}
                  style={{ cursor: 'pointer' }}
                >
                  {option.label}
                </Tag>
              );
            })}
          </div>
          <Text as="p" variant="meta" tone="secondary" style={{ marginTop: 0, marginBottom: SPACE.x16 }}>
            Leave every scope off to allow host, environment, application, and wave exports.
          </Text>
          {selectedTemplate?.id ? (
            <div>
              <Button onClick={onDuplicateTemplate}>Duplicate template</Button>
              <Text as="p" variant="meta" tone="secondary" style={{ marginTop: SPACE.x8 }}>
                Creates a new custom template from this design. The org brand kit stays shared.
              </Text>
            </div>
          ) : null}
        </div>
      ) : null}

      {page === 'design' ? (
        <div>
          <SectionHeader title={selectedTemplate?.name || 'New report template'}>
            <Button size="small" variant="contained" disabled={!formDirty} onClick={onSaveTemplate}>
              {formDirty ? 'Save changes' : 'Saved'}
            </Button>
          </SectionHeader>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: SPACE.x16, marginBottom: SPACE.x16 }}>
            <BoundTokenField
              label="Header"
              fieldId="branding.header_text"
              value={templateForm.branding?.header_text}
              onChange={(value) => setBranding({ header_text: value })}
              onFocusField={onFocusField}
            />
            <BoundTokenField
              label="Footer"
              fieldId="branding.footer_text"
              value={templateForm.branding?.footer_text}
              onChange={(value) => setBranding({ footer_text: value })}
              onFocusField={onFocusField}
            />
            <BoundTokenField
              label="Classification"
              fieldId="branding.classification"
              value={templateForm.branding?.classification}
              onChange={(value) => setBranding({ classification: value })}
              onFocusField={onFocusField}
            />
            <BoundTokenField
              label="Report title"
              fieldId="placeholders.report_title"
              value={templateForm.placeholders?.report_title}
              onChange={(value) => setPlaceholders({ report_title: value })}
              onFocusField={onFocusField}
            />
            <BoundTokenField
              label="Subtitle"
              fieldId="placeholders.report_subtitle"
              value={templateForm.placeholders?.report_subtitle}
              onChange={(value) => setPlaceholders({ report_subtitle: value })}
              onFocusField={onFocusField}
            />
            <BoundTokenField
              label="Prepared by"
              fieldId="placeholders.prepared_by"
              value={templateForm.placeholders?.prepared_by}
              onChange={(value) => setPlaceholders({ prepared_by: value })}
              onFocusField={onFocusField}
            />
            <BoundTokenField
              label="Prepared for"
              fieldId="placeholders.prepared_for"
              value={templateForm.placeholders?.prepared_for}
              onChange={(value) => setPlaceholders({ prepared_for: value })}
              onFocusField={onFocusField}
            />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 0 }}>
              <span style={{ ...TYPE.micro, color: palette.textTertiary, visibility: 'hidden' }}>Edit template</span>
              <Button
                variant="contained"
                onClick={openEditor}
                style={{
                  width: '100%',
                  height: 40,
                  minHeight: 40,
                  boxSizing: 'border-box',
                  border: `1px solid ${palette.accentLine}`,
                  boxShadow: `0 0 0 1px ${palette.accentFill}`
                }}
              >
                Edit template
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      <Panel open={editorOpen} onClose={requestCloseEditor} maxWidth="xl">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <Button size="small" onClick={requestCloseEditor}>
            Close
          </Button>
          <Text variant="bodyStrong">Template editor</Text>
          <Button size="small" variant="contained" disabled={!editorDirty} onClick={saveEditor}>
            {editorDirty ? 'Save changes' : 'Saved'}
          </Button>
        </div>
        <TemplateEditorCanvas
          blocks={blocks}
          selectedBlockId={selectedBlockId}
          selectedBlock={selectedBlock}
          coverCount={coverCount}
          previewKind={previewKind}
          brandKit={brandKit}
          templateForm={templateForm}
          TokenField={BoundTokenField}
          onFocusField={onFocusField}
          onAddBlock={addBlock}
          onMoveBlock={moveBlock}
          onRemoveBlock={removeBlock}
          onSelectBlock={setSelectedBlockId}
          onPreviewKindChange={setPreviewKind}
          onUpdateSelectedBlock={updateSelectedBlock}
        />
      </Panel>

      <Panel
        open={discardOpen}
        onClose={() => setDiscardOpen(false)}
        maxWidth="xs"
        title="Discard template edits?"
        actions={
          <>
            <Button onClick={() => setDiscardOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={discardEditor}>
              Discard
            </Button>
          </>
        }
      >
        <Text variant="body" tone="secondary">
          Clicking outside or closing the editor will drop unsaved block changes. Chrome fields on Template design stay
          as they are.
        </Text>
      </Panel>
    </div>
  );
};

export default ReportTemplatesSection;
