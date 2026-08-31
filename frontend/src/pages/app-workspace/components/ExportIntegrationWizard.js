import React, { useEffect, useMemo, useState } from 'react';
import { Button, Combo, Field, Panel, Tag, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { isMultiValue, optionHasChoices } from '../../admin-settings/integrations-utils';
import { exportToIntegration, previewIntegrationExport } from '../services';

const KIND_LABEL = { jira: 'Jira', defectdojo: 'DefectDojo' };

const optionList = (values = []) =>
  (values || []).map((item) => ({
    value: item.id || item.value,
    label: item.label || item.value || item.id
  }));

const ExportIntegrationWizard = ({
  open,
  kind,
  appId,
  waveId,
  waveName,
  findings = [],
  ready,
  onClose,
  onDone,
  failWith,
  notify
}) => {
  const [step, setStep] = useState('fields');
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const [extras, setExtras] = useState({});
  const [results, setResults] = useState(null);
  const [templateId, setTemplateId] = useState('');

  const label = KIND_LABEL[kind] || 'integration';
  const templateOptions = (ready?.connections || [])
    .filter((connection) => connection.kind === kind)
    .flatMap((connection) =>
      (connection.templates || []).map((template) => ({
        value: String(template.id),
        label: `${template.name}${template.is_default ? ' (default)' : ''}`
      }))
    );

  useEffect(() => {
    if (!open) {
      setPreview(null);
      setResults(null);
      setExtras({});
      setStep('fields');
      setTemplateId('');
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    const findingIds = findings.map((item) => item.id).filter(Boolean);
    previewIntegrationExport({
      kind,
      template_id: templateId || undefined,
      finding_ids: findingIds,
      wave_id: waveId || undefined,
      application_id: appId || undefined
    })
      .then((res) => {
        if (cancelled) return;
        const data = res.data;
        setPreview(data);
        const reportable = (data.findings || []).filter(
          (item) => !item.already_exported && item.status !== 'draft'
        );
        let nextIds = reportable.map((item) => item.id);
        if (!nextIds.length && !waveId && (data.findings || []).length === 1) {
          const only = data.findings[0];
          if (only?.id && only.status !== 'draft') nextIds = [only.id];
        }
        setSelectedIds(nextIds);
        const seed = {};
        (data.ask || []).forEach((field) => {
          if (field.static_value) seed[field.external_field_id] = field.static_value;
        });
        setExtras(seed);
        const manyFindings = (data.findings || []).length > 1;
        setStep(manyFindings ? 'findings' : (data.ask || []).length ? 'fields' : 'review');
      })
      .catch((error) => {
        if (!cancelled) failWith(error, `Failed to prepare the ${label} report.`);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, kind, appId, waveId, templateId, findings.map((item) => item.id).join(',')]);

  const askFields = preview?.ask || [];
  const missingRequired = askFields.filter((field) => {
    if (!field.required) return false;
    const value = extras[field.external_field_id];
    return value === undefined || value === '' || (Array.isArray(value) && value.length === 0);
  });

  const selectedFindings = useMemo(
    () => (preview?.findings || []).filter((item) => selectedIds.includes(item.id)),
    [preview, selectedIds]
  );

  const toggleFinding = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  };

  const handleSend = async () => {
    if (!selectedIds.length) {
      notify('error', 'Select at least one finding.');
      return;
    }
    if (missingRequired.length) {
      notify('error', `Fill ${missingRequired[0].external_field_name} before sending.`);
      setStep('fields');
      return;
    }
    setSending(true);
    try {
      const res = await exportToIntegration({
        kind,
        template_id: preview?.template?.id,
        finding_ids: selectedIds,
        extras,
        wave_id: waveId || undefined,
        wave_name: waveName || undefined,
        application_id: appId || undefined
      });
      setResults(res.data);
      setStep('done');
      const created = res.data.created || 0;
      const failed = res.data.failed || 0;
      if (failed && !created) notify('error', `Nothing reached ${label}.`);
      else if (failed) notify('error', `${created} sent, ${failed} failed.`);
      else notify('success', created === 1 ? `Sent to ${label}.` : `Sent ${created} findings to ${label}.`);
      await onDone?.(res.data);
    } catch (error) {
      failWith(error, `Failed to send to ${label}.`);
    } finally {
      setSending(false);
    }
  };

  const title = waveId ? `Report wave to ${label}` : `Report to ${label}`;

  const actions = (() => {
    if (step === 'done') {
      return (
        <Button variant="contained" onClick={onClose}>
          Done
        </Button>
      );
    }
    if (step === 'findings') {
      return (
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="contained" onClick={() => setStep(askFields.length ? 'fields' : 'review')} disabled={!selectedIds.length}>
            Continue
          </Button>
        </>
      );
    }
    if (step === 'fields') {
      return (
        <>
          {preview?.findings?.length > 1 ? <Button onClick={() => setStep('findings')}>Back</Button> : <Button onClick={onClose}>Cancel</Button>}
          <Button variant="contained" onClick={() => setStep('review')}>
            Review
          </Button>
        </>
      );
    }
    return (
      <>
        <Button onClick={() => setStep(askFields.length ? 'fields' : 'findings')}>Back</Button>
        <Button variant="contained" onClick={handleSend} disabled={sending || !selectedIds.length}>
          {sending ? 'Sending…' : `Send to ${label}`}
        </Button>
      </>
    );
  })();

  return (
    <Panel open={open} onClose={onClose} title={title} maxWidth="md" actions={actions}>
      {loading ? (
        <Text variant="meta" tone="secondary">
          Reading the {label} template…
        </Text>
      ) : null}

      {preview && !loading && step !== 'done' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Text variant="meta" tone="secondary">
            {preview.template?.name} · {preview.connection?.base_url}
          </Text>
          {templateOptions.length > 1 ? (
            <Combo
              label="Template"
              options={templateOptions}
              value={templateId || String(preview.template?.id || '')}
              onChange={setTemplateId}
            />
          ) : null}
        </div>
      ) : null}

      {preview?.refresh_warning ? (
        <Text variant="meta" tone="critical">
          Using the last saved field list. {preview.refresh_warning}
        </Text>
      ) : null}

      {step === 'findings' && preview ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Text variant="bodyStrong">Findings to send</Text>
          {(preview.findings || []).map((item) => (
            <label key={item.id} style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={selectedIds.includes(item.id)}
                disabled={Boolean(item.already_exported)}
                onChange={() => {
                  if (item.already_exported) return;
                  toggleFinding(item.id);
                }}
              />
              <span style={{ minWidth: 0 }}>
                <Text as="span" variant="bodyStrong">
                  {item.title}
                </Text>
                <span style={{ display: 'inline-flex', gap: 6, marginLeft: 8 }}>
                  <Tag>{item.severity}</Tag>
                  {item.already_exported ? <Tag>already sent</Tag> : null}
                </span>
              </span>
            </label>
          ))}
          {(preview.findings || []).every((item) => item.already_exported || item.status === 'draft') ? (
            <Text variant="meta" tone="secondary">
              Every finding here already has a {label} ticket.
            </Text>
          ) : null}
        </div>
      ) : null}

      {step === 'fields' && preview ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x16 }}>
          {preview.mapped?.length ? (
            <div>
              <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
                Filled from RAPTOR
              </Text>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {preview.mapped.map((item) => (
                  <div key={item.external_field_id} style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
                    <Text variant="meta" tone="secondary">
                      {item.external_field_name}
                    </Text>
                    <Text
                      variant="meta"
                      style={{
                        textAlign: 'right',
                        whiteSpace: 'pre-wrap',
                        maxWidth: 360,
                        display: '-webkit-box',
                        WebkitLineClamp: 6,
                        WebkitBoxOrient: 'vertical',
                        overflow: 'hidden'
                      }}
                    >
                      {String(item.preview || '—')}
                    </Text>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {askFields.length === 0 ? (
            <Text variant="meta" tone="secondary">
              Every required {label} field is already mapped. Review and send.
            </Text>
          ) : (
            askFields.map((field) => {
              const value = extras[field.external_field_id] ?? (isMultiValue(field.type) ? [] : '');
              if (optionHasChoices(field.type)) {
                return (
                  <Combo
                    key={field.external_field_id}
                    label={`${field.external_field_name}${field.required ? '' : ' (optional)'}`}
                    options={optionList(field.allowed_values)}
                    multiple={isMultiValue(field.type)}
                    value={value}
                    onChange={(next) => setExtras((prev) => ({ ...prev, [field.external_field_id]: next }))}
                  />
                );
              }
              return (
                <Field
                  key={field.external_field_id}
                  label={`${field.external_field_name}${field.required ? '' : ' (optional)'}`}
                  value={value}
                  onChange={(event) =>
                    setExtras((prev) => ({ ...prev, [field.external_field_id]: event.target.value }))
                  }
                />
              );
            })
          )}
        </div>
      ) : null}

      {step === 'review' && preview ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Text variant="bodyStrong">
            {selectedFindings.length} finding{selectedFindings.length === 1 ? '' : 's'} → {label}
          </Text>
          {selectedFindings.map((item) => (
            <Text key={item.id} as="div" variant="meta">
              {item.title}
            </Text>
          ))}
          {askFields.length ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8 }}>
              {askFields.map((field) => (
                <div
                  key={field.external_field_id}
                  style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'baseline' }}
                >
                  <Text as="div" variant="meta" tone="secondary">
                    {field.external_field_name}
                  </Text>
                  <Text as="div" variant="meta" style={{ textAlign: 'right' }}>
                    {formatExtra(extras[field.external_field_id], field)}
                  </Text>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {step === 'done' && results ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {(results.results || []).map((item) => (
            <div key={`${item.id}-${item.external_id || item.error}`} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
              <Text variant="meta">{item.title || item.id}</Text>
              {item.status === 'created' && item.external_url ? (
                <Text as="a" variant="meta" href={item.external_url} target="_blank" rel="noreferrer">
                  {item.external_id}
                </Text>
              ) : (
                <Text variant="meta" tone="critical">
                  {item.error || item.status}
                </Text>
              )}
            </div>
          ))}
        </div>
      ) : null}
    </Panel>
  );
};

const formatExtra = (value, field) => {
  if (value == null || value === '') return '—';
  if (Array.isArray(value)) {
    const labels = optionList(field.allowed_values);
    return value
      .map((item) => labels.find((option) => option.value === item)?.label || item)
      .join(', ');
  }
  const match = optionList(field.allowed_values).find((option) => option.value === value);
  return match?.label || String(value);
};

export default ExportIntegrationWizard;
