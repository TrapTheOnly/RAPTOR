import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Checkbox, CircularProgress, LinearProgress } from '@mui/material';
import { Description, GppGood, Lock, WarningAmber } from '@mui/icons-material';
import {
  Button,
  Combo,
  EnvTag,
  Field,
  Metric,
  Panel,
  Rule,
  Surface,
  Tag,
  Text,
  severityKeyFromScore
} from '../../../design/primitives';
import { EXPORT_PACKAGES, packageMeta } from '../../../theme/tokens';
import { SPACE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';

const SEVERITY_FLOOR_OPTIONS = [
  { value: '0', label: 'Everything' },
  { value: '4', label: '4.0 and above' },
  { value: '7', label: '7.0 and above' },
  { value: '9', label: '9.0 and above' }
];

const waveEnvIds = (wave) => {
  const raw = wave?.env_ids?.length ? wave.env_ids : wave?.environment_id ? [wave.environment_id] : [];
  return raw.map((id) => Number(id)).filter((id) => Number.isFinite(id));
};

const EMPTY_TEMPLATES = [];

const ExportSheetDialog = ({
  open,
  onClose,
  environments = [],
  defaultEnvIds = [],
  waves = [],
  zones = [],
  canExport,
  generating,
  onGenerate,
  onPreview,
  defaultPackage = 'owner_delivery',
  scopeLabel,
  lockedWave = null,
  templates = EMPTY_TEMPLATES
}) => {
  const palette = usePalette();
  const ending = Boolean(lockedWave);
  const [packageKey, setPackageKey] = useState(ending ? 'wave_archive' : defaultPackage);
  const [waveId, setWaveId] = useState(lockedWave?.id || '');
  const [selectedEnvIds, setSelectedEnvIds] = useState(defaultEnvIds);
  const [severityFloor, setSeverityFloor] = useState('0');
  const [hostPrefix, setHostPrefix] = useState('');
  const [hostSuffix, setHostSuffix] = useState('');
  const [includeDrafts, setIncludeDrafts] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [templateId, setTemplateId] = useState('');

  useEffect(() => {
    if (!open) return;
    const nextPackage = lockedWave ? 'wave_archive' : defaultPackage;
    const nextWaveId = lockedWave?.id || '';
    const nextEnvs = lockedWave ? waveEnvIds(lockedWave) : defaultEnvIds;
    setPackageKey(nextPackage);
    setWaveId(nextWaveId);
    setSelectedEnvIds(nextEnvs);
    setSeverityFloor('0');
    setHostPrefix('');
    setHostSuffix('');
    setIncludeDrafts(nextPackage === 'internal_draft');
    setConfirmed(false);
    setPreview(null);
    setTemplateId(templates[0] ? String(templates[0].id) : '');
  }, [open, defaultEnvIds, defaultPackage, lockedWave, templates]);

  const selectableEnvs = useMemo(() => {
    const available = environments.filter((env) => env.slug !== 'unassigned');
    if (!lockedWave) return available;
    const allowed = new Set(waveEnvIds(lockedWave).map(String));
    return available.filter((env) => allowed.has(String(env.id)));
  }, [environments, lockedWave]);
  const openWaves = useMemo(() => waves.filter((wave) => wave.status === 'open'), [waves]);

  const requestPayload = useMemo(
    () => ({
      package: packageKey,
      wave_id: waveId || undefined,
      selected_env_ids: selectedEnvIds,
      include_drafts: packageKey === 'internal_draft' ? includeDrafts : false,
      severity_floor: Number(severityFloor || 0),
      host_prefix: hostPrefix,
      host_suffix: hostSuffix,
      template_id: templateId ? Number(templateId) : undefined
    }),
    [packageKey, waveId, selectedEnvIds, includeDrafts, severityFloor, hostPrefix, hostSuffix, templateId]
  );

  const packageReady = packageKey !== 'wave_archive' || Boolean(waveId);
  const templateReady = templates.length === 0 || Boolean(templateId);
  const canSubmit =
    canExport && confirmed && !generating && selectedEnvIds.length > 0 && packageReady && templateReady;

  const runPreview = useCallback(async () => {
    if (!open || !onPreview || selectedEnvIds.length === 0 || !packageReady) {
      setPreview(null);
      return;
    }
    setPreviewLoading(true);
    try {
      const response = await onPreview(requestPayload);
      setPreview(response?.data || null);
    } catch (error) {
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [open, onPreview, requestPayload, selectedEnvIds.length, packageReady]);

  useEffect(() => {
    const handle = setTimeout(runPreview, 350);
    return () => clearTimeout(handle);
  }, [runPreview]);

  const toggleEnv = (envId) => {
    setSelectedEnvIds((prev) =>
      prev.includes(envId) ? prev.filter((id) => id !== envId) : [...prev, envId]
    );
  };

  const handlePackageChange = (nextPackage) => {
    setPackageKey(nextPackage);
    setIncludeDrafts(nextPackage === 'internal_draft');
    if (nextPackage === 'owner_delivery') setSelectedEnvIds(defaultEnvIds);
    if (nextPackage !== 'wave_archive') setWaveId('');
  };

  const handleWaveChange = (nextWaveId) => {
    setWaveId(nextWaveId);
    const wave = waves.find((item) => String(item.id) === String(nextWaveId));
    if (wave && Array.isArray(wave.env_ids) && wave.env_ids.length) {
      setSelectedEnvIds(wave.env_ids.map((id) => Number(id)));
    }
  };

  const meta = packageMeta(packageKey);
  const unassignedHosts = preview?.unassigned_in_scope_hosts || [];
  const watermark = preview?.watermark;

  return (
    <Panel
      open={open}
      onClose={onClose}
      maxWidth="md"
      title={ending ? `End “${lockedWave.name}”` : 'Export sheet'}
      actions={
        <>
          <label style={{ marginRight: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
            <Checkbox
              size="small"
              checked={confirmed}
              onChange={(event) => setConfirmed(event.target.checked)}
            />
            <Text variant="body">I confirm this export scope</Text>
          </label>
          <Button onClick={onClose}>Cancel</Button>
          <Button
            variant="contained"
            disabled={!canSubmit}
            onClick={() => onGenerate(requestPayload)}
            startIcon={generating ? <CircularProgress size={14} color="inherit" /> : <Description />}
          >
            {generating
              ? ending
                ? 'Ending…'
                : 'Generating…'
              : ending
                ? 'End and export'
                : `Generate ${meta.label.toLowerCase()}`}
          </Button>
        </>
      }
    >
      <Text variant="meta" tone="secondary">
        {ending
          ? 'Exports every finding on this wave, then freezes the engagement. It cannot be reopened.'
          : `${scopeLabel || 'Application scope'} · one sheet, four named exports`}
      </Text>

      <div
        style={{
          display: 'grid',
          gap: 24,
          gridTemplateColumns: 'minmax(0, 3fr) minmax(0, 2fr)'
        }}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {ending ? (
            <>
              <Field
                label="Export"
                value="Wave archive — every finding on this engagement"
                disabled
              />
              <Field label="Wave" value={lockedWave.name} disabled />
            </>
          ) : (
            <Combo
              label="Export"
              mode="enum"
              options={EXPORT_PACKAGES.map((item) => ({ value: item.key, label: item.label }))}
              value={packageKey}
              onChange={handlePackageChange}
              hint={meta.blurb}
            />
          )}

          {packageKey === 'wave_archive' && !ending ? (
            <Combo
              label="Wave"
              mode="enum"
              options={openWaves.map((wave) => ({ value: wave.id, label: wave.name }))}
              value={waveId}
              disableClearable={false}
              placeholder={openWaves.length === 0 ? 'No open waves' : 'Choose a wave'}
              onChange={handleWaveChange}
            />
          ) : null}

          {templates.length > 0 ? (
            <Combo
              label="Report template"
              mode="enum"
              options={templates.map((item) => ({
                value: String(item.id),
                label: item.name || `Template ${item.id}`
              }))}
              value={templateId}
              onChange={setTemplateId}
            />
          ) : null}

          <div>
            <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 8 }}>
              Environments
            </Text>
            {ending ? (
              <Text as="p" variant="meta" tone="secondary" style={{ margin: '0 0 8px' }}>
                Every environment on this wave is included. They cannot be changed while ending.
              </Text>
            ) : null}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {selectableEnvs.map((env) => (
                <label
                  key={env.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    minHeight: 32,
                    cursor: ending ? 'default' : 'pointer'
                  }}
                >
                  <Checkbox
                    size="small"
                    checked={selectedEnvIds.map(Number).includes(Number(env.id))}
                    disabled={ending}
                    onChange={() => toggleEnv(env.id)}
                  />
                  <EnvTag slug={env.slug} label={env.slug} />
                  <Text variant="body">{env.display_name}</Text>
                  {env.include_in_exec_report ? (
                    <Lock sx={{ fontSize: 13, color: palette.textTertiary }} titleAccess="Pre-checked by configuration" />
                  ) : null}
                </label>
              ))}
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
            <Combo
              label="Severity floor"
              mode="enum"
              options={SEVERITY_FLOOR_OPTIONS}
              value={severityFloor}
              onChange={setSeverityFloor}
            />
            <Field
              label="Host prefix"
              placeholder="api-"
              value={hostPrefix}
              onChange={(event) => setHostPrefix(event.target.value)}
            />
            <Combo
              label="Host domain"
              mode="enum"
              options={[
                { value: '', label: 'Every host' },
                ...zones.map((zone) => {
                  const suffix = `.${String(zone.suffix || '').replace(/^\./, '')}`;
                  return { value: suffix, label: suffix };
                })
              ]}
              value={hostSuffix}
              onChange={setHostSuffix}
            />
          </div>

          {packageKey === 'internal_draft' ? (
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 32, cursor: 'pointer' }}>
              <Checkbox
                size="small"
                checked={includeDrafts}
                onChange={(event) => setIncludeDrafts(event.target.checked)}
              />
              <Text variant="body">Include draft findings</Text>
            </label>
          ) : null}
        </div>

        <Surface style={{ padding: SPACE.x16, alignSelf: 'start' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <Text variant="micro" tone="tertiary">
              Live preview
            </Text>
            {previewLoading ? <CircularProgress size={14} /> : null}
          </div>

          {previewLoading && !preview ? <LinearProgress style={{ marginBottom: 12 }} /> : null}

          {!preview && !previewLoading ? (
            <Text variant="body" tone="secondary">
              {selectedEnvIds.length === 0
                ? 'Pick at least one environment to see what this export will contain.'
                : 'Scope is set. Confirm below to generate.'}
            </Text>
          ) : preview ? (
            <>
              <div style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                <Metric value={preview.finding_count ?? 0} />
                <Text variant="body" tone="secondary">
                  finding{preview.finding_count === 1 ? '' : 's'}
                </Text>
              </div>

              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 12 }}>
                {watermark ? <Tag emphasized={watermark === 'PRODUCTION'}>{watermark}</Tag> : null}
                {Number(preview.excluded_draft_count || 0) > 0 ? (
                  <Tag>
                    {preview.excluded_draft_count} draft{preview.excluded_draft_count === 1 ? '' : 's'} excluded
                  </Tag>
                ) : null}
              </div>

              {preview.findings?.length > 0 ? (
                <>
                  <Rule style={{ margin: '12px 0' }} />
                  <div style={{ maxHeight: 220, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {preview.findings.map((item) => (
                      <div key={item.id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span
                          aria-hidden
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: 99,
                            flexShrink: 0,
                            background: palette.severity[severityKeyFromScore(item.baseScore)]
                          }}
                        />
                        <Text variant="bodyStrong" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {item.title || 'Untitled'}
                        </Text>
                        {item.also_observed?.length > 0 ? <Tag>+{item.also_observed.length}</Tag> : null}
                      </div>
                    ))}
                  </div>
                </>
              ) : null}

              {preview.finding_count === 0 ? (
                <Alert severity="warning" icon={<WarningAmber />} style={{ marginTop: 12 }}>
                  Nothing matches this scope. The PDF would be empty.
                </Alert>
              ) : null}

              {unassignedHosts.length > 0 ? (
                <Alert severity="warning" style={{ marginTop: 12 }}>
                  <Text as="div" variant="bodyStrong">
                    {unassignedHosts.length} unassigned in-scope host(s) excluded
                  </Text>
                  <Text as="div" variant="meta" tone="secondary">
                    {unassignedHosts
                      .slice(0, 4)
                      .map((host) => host.name || host.record_id)
                      .join(', ')}
                    {unassignedHosts.length > 4 ? ` +${unassignedHosts.length - 4} more` : ''}
                  </Text>
                </Alert>
              ) : null}
            </>
          ) : null}

          <Rule style={{ margin: '12px 0' }} />
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <GppGood sx={{ fontSize: 16, color: palette.textTertiary, marginTop: 2 }} />
            <Text variant="meta" tone="secondary">
              Generating freezes an immutable export row and signs its content hash with HMAC-SHA256. Notes and
              credential pointers are never rendered.
            </Text>
          </div>
        </Surface>
      </div>
    </Panel>
  );
};

export default ExportSheetDialog;
