import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Hub } from '@mui/icons-material';
import {
  Button,
  Combo,
  EmptyState,
  Field,
  Surface,
  Tag,
  Tabs,
  Text
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import {
  ENGAGEMENT_MODES,
  KIND_META,
  TEST_MODES
} from '../integrations-utils';
import FieldMappingEditor from './integrations/FieldMappingEditor';

const FORM_GRID = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
  gap: SPACE.x16,
  alignItems: 'start'
};

const ACTIONS = {
  display: 'flex',
  flexWrap: 'wrap',
  gap: 8,
  alignItems: 'center'
};

const emptyForm = (kind) => ({
  name: '',
  base_url: '',
  auth_email: '',
  api_token: '',
  auth_type: kind === 'jira' ? 'api_token' : 'api_key'
});

const IntegrationsSection = ({ showMessage }) => {
  const [kind, setKind] = useState('jira');
  const [meta, setMeta] = useState({ raptor_fields: [] });
  const [connections, setConnections] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState(emptyForm('jira'));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [catalog, setCatalog] = useState({ projects: [], issueTypes: [], products: [], engagements: [], tests: [] });
  const [draft, setDraft] = useState({
    project: '',
    issueType: '',
    product: '',
    engagementMode: 'per_wave',
    engagementId: '',
    testMode: 'create',
    testId: '',
    name: ''
  });
  const [selectedTemplateId, setSelectedTemplateId] = useState(null);
  const [mappings, setMappings] = useState([]);
  const [busy, setBusy] = useState('');

  const kindConnections = useMemo(
    () => connections.filter((item) => item.kind === kind),
    [connections, kind]
  );
  const selected = kindConnections.find((item) => String(item.id) === String(selectedId)) || kindConnections[0] || null;
  const templates = detail?.templates || [];
  const selectedTemplate = templates.find((item) => String(item.id) === String(selectedTemplateId)) || templates[0] || null;
  const metaCopy = KIND_META[kind];

  const loadConnections = useCallback(async () => {
    const [metaRes, listRes] = await Promise.all([
      axios.get('/api/integrations/meta'),
      axios.get('/api/integrations')
    ]);
    setMeta(metaRes.data || { raptor_fields: [] });
    setConnections(listRes.data?.connections || []);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadConnections()
      .catch((error) => showMessage('error', error.response?.data?.error || 'Failed to load integrations.'))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadConnections, showMessage]);

  useEffect(() => {
    setForm(emptyForm(kind));
    setCatalog({ projects: [], issueTypes: [], products: [], engagements: [], tests: [] });
    setSelectedTemplateId(null);
    setMappings([]);
  }, [kind]);

  useEffect(() => {
    const match = connections.find((item) => item.kind === kind);
    setSelectedId((current) => {
      if (current && connections.some((item) => String(item.id) === String(current) && item.kind === kind)) {
        return current;
      }
      return match?.id || null;
    });
  }, [kind, connections]);

  const loadDetail = useCallback(
    async (connectionId) => {
      if (!connectionId) {
        setDetail(null);
        return;
      }
      const res = await axios.get(`/api/integrations/${connectionId}`);
      setDetail(res.data);
      const first = res.data?.templates?.[0];
      setSelectedTemplateId(first?.id || null);
      setMappings(first?.mappings || []);
    },
    []
  );

  useEffect(() => {
    if (!selected?.id) {
      setDetail(null);
      return undefined;
    }
    let cancelled = false;
    loadDetail(selected.id).catch((error) => {
      if (!cancelled) showMessage('error', error.response?.data?.error || 'Failed to load integration.');
    });
    return () => {
      cancelled = true;
    };
  }, [selected?.id, loadDetail, showMessage]);

  useEffect(() => {
    if (!selectedTemplate) {
      setMappings([]);
      return;
    }
    setMappings(selectedTemplate.mappings || []);
    const extra = selectedTemplate.extra || {};
    setDraft((prev) => ({
      ...prev,
      name: selectedTemplate.name || '',
      project: selectedTemplate.external_project_key || '',
      issueType: selectedTemplate.issue_type_id || '',
      product: extra.product_id || selectedTemplate.external_project_key || '',
      engagementMode: extra.engagement_mode || 'per_wave',
      engagementId: extra.engagement_id || '',
      testMode: extra.test_mode || 'create',
      testId: extra.test_id || ''
    }));
  }, [selectedTemplate?.id]);

  const loadJiraProjects = useCallback(async (connectionId) => {
    const res = await axios.get(`/api/integrations/${connectionId}/catalog/projects`);
    setCatalog((prev) => ({ ...prev, projects: res.data.projects || [] }));
  }, []);

  const loadJiraTypes = useCallback(async (connectionId, project) => {
    const res = await axios.get(`/api/integrations/${connectionId}/catalog/issue-types`, { params: { project } });
    setCatalog((prev) => ({ ...prev, issueTypes: res.data.issue_types || [] }));
  }, []);

  const loadDojoCatalog = useCallback(async (connectionId) => {
    const res = await axios.get(`/api/integrations/${connectionId}/catalog/products`);
    setCatalog((prev) => ({ ...prev, products: res.data.products || [] }));
  }, []);

  useEffect(() => {
    if (!selected?.id || selected.status !== 'connected') return undefined;
    let cancelled = false;
    const run = kind === 'jira' ? loadJiraProjects(selected.id) : loadDojoCatalog(selected.id);
    run.catch((error) => {
      if (!cancelled) showMessage('error', error.response?.data?.error || 'Failed to load catalog.');
    });
    return () => {
      cancelled = true;
    };
  }, [selected?.id, selected?.status, kind, showMessage, loadJiraProjects, loadDojoCatalog]);

  useEffect(() => {
    if (kind !== 'jira' || !selected?.id || !draft.project) return undefined;
    let cancelled = false;
    loadJiraTypes(selected.id, draft.project).catch((error) => {
      if (!cancelled) showMessage('error', error.response?.data?.error || 'Failed to load issue types.');
    });
    return () => {
      cancelled = true;
    };
  }, [kind, selected?.id, draft.project, showMessage, loadJiraTypes]);

  useEffect(() => {
    if (kind !== 'defectdojo' || !selected?.id || !draft.product) return undefined;
    let cancelled = false;
    axios
      .get(`/api/integrations/${selected.id}/catalog/engagements`, { params: { product: draft.product } })
      .then((res) => setCatalog((prev) => ({ ...prev, engagements: res.data.engagements || [] })))
      .catch((error) => {
        if (!cancelled) showMessage('error', error.response?.data?.error || 'Failed to load engagements.');
      });
    return () => {
      cancelled = true;
    };
  }, [kind, selected?.id, draft.product, showMessage]);

  const handleConnect = async () => {
    if (!form.base_url.trim() || !form.api_token.trim()) {
      showMessage('error', 'URL and API key are required.');
      return;
    }
    setSaving(true);
    try {
      const res = await axios.post('/api/integrations', {
        kind,
        name: form.name.trim() || metaCopy.label,
        base_url: form.base_url.trim(),
        auth_email: form.auth_email.trim(),
        auth_type: form.auth_type,
        api_token: form.api_token.trim()
      });
      if (res.data.error) {
        showMessage('error', res.data.error);
      } else {
        showMessage('success', `${metaCopy.label} connected.`);
      }
      await loadConnections();
      if (res.data.connection?.id) setSelectedId(res.data.connection.id);
      setForm(emptyForm(kind));
    } catch (error) {
      showMessage('error', error.response?.data?.error || `Failed to connect ${metaCopy.label}.`);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!selected) return;
    setBusy('test');
    try {
      const res = await axios.post(`/api/integrations/${selected.id}/test`);
      showMessage(res.data.error ? 'error' : 'success', res.data.error || `Connection established.`);
      await loadConnections();
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Connection test failed.');
    } finally {
      setBusy('');
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    setBusy('delete');
    try {
      await axios.delete(`/api/integrations/${selected.id}`);
      showMessage('success', `${metaCopy.label} disconnected.`);
      await loadConnections();
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to remove integration.');
    } finally {
      setBusy('');
    }
  };

  const handleCreateTemplate = async () => {
    if (!selected) return;
    setBusy('template');
    try {
      const body =
        kind === 'jira'
          ? {
            name: draft.name.trim(),
            external_project_key: draft.project,
            external_project_name: catalog.projects.find((item) => item.key === draft.project)?.name || draft.project,
            issue_type_id: draft.issueType,
            issue_type_name: catalog.issueTypes.find((item) => item.id === draft.issueType)?.name || draft.issueType,
            is_default: templates.length === 0
          }
          : {
            name: draft.name.trim(),
            extra: {
              product_id: draft.product,
              product_name: catalog.products.find((item) => String(item.id) === String(draft.product))?.name || draft.product,
              engagement_mode: draft.engagementMode,
              engagement_id: draft.engagementId,
              test_mode: draft.testMode,
              test_id: draft.testId,
              test_title: 'RAPTOR'
            },
            is_default: templates.length === 0
          };
      const res = await axios.post(`/api/integrations/${selected.id}/templates`, body);
      showMessage('success', `${metaCopy.templateNoun} saved.`);
      await loadDetail(selected.id);
      setSelectedTemplateId(res.data.template?.id);
      setMappings(res.data.template?.mappings || []);
    } catch (error) {
      showMessage('error', error.response?.data?.error || `Failed to save ${metaCopy.templateNoun}.`);
    } finally {
      setBusy('');
    }
  };

  const handleSaveMappings = async () => {
    if (!selected || !selectedTemplate) return;
    setBusy('map');
    try {
      await axios.put(`/api/integrations/${selected.id}/templates/${selectedTemplate.id}/mappings`, { mappings });
      showMessage('success', 'Field mapping saved.');
      await loadDetail(selected.id);
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to save mapping.');
    } finally {
      setBusy('');
    }
  };

  const handleRefreshFields = async () => {
    if (!selected || !selectedTemplate) return;
    setBusy('refresh');
    try {
      const res = await axios.patch(`/api/integrations/${selected.id}/templates/${selectedTemplate.id}`, {
        refresh_fields: true
      });
      setMappings(res.data.template?.mappings || []);
      showMessage('success', 'Fields refreshed from the remote template.');
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to refresh fields.');
    } finally {
      setBusy('');
    }
  };

  const handleSetDefault = async (template) => {
    if (!selected) return;
    await axios.patch(`/api/integrations/${selected.id}/templates/${template.id}`, { is_default: true });
    await loadDetail(selected.id);
  };

  if (loading) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x24 }}>
      <Tabs
        value={kind}
        onChange={setKind}
        items={[
          { value: 'jira', label: 'Jira' },
          { value: 'defectdojo', label: 'DefectDojo' }
        ]}
      />

      <Surface style={{ padding: SPACE.x24 }}>
        <Text as="h2" variant="h2" style={{ margin: 0 }}>
          {selected ? `${metaCopy.label} connection` : `Connect ${metaCopy.label}`}
        </Text>
        <Text as="p" variant="meta" tone="secondary" style={{ margin: '8px 0 0' }}>
          {metaCopy.connectHint}
        </Text>

        {selected ? (
          <div style={{ marginTop: SPACE.x16, display: 'flex', flexDirection: 'column', gap: SPACE.x12 }}>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <Tag emphasized={selected.status === 'connected'}>{selected.status}</Tag>
              <Text variant="meta" tone="secondary">
                {selected.base_url}
              </Text>
              {selected.auth_email ? (
                <Text variant="meta" tone="secondary">
                  {selected.auth_email}
                </Text>
              ) : null}
            </div>
            {selected.last_error ? (
              <Text variant="meta" tone="critical">
                {selected.last_error}
              </Text>
            ) : null}
            <div style={{ ...FORM_GRID, marginTop: SPACE.x16 }}>
              <Field
                label="Replace API key"
                type="password"
                value={form.api_token}
                onChange={(event) => setForm((prev) => ({ ...prev, api_token: event.target.value }))}
                autoComplete="new-password"
              />
            </div>
            <div style={{ ...ACTIONS, marginTop: SPACE.x12 }}>
              <Button
                size="small"
                disabled={!form.api_token.trim() || busy === 'rotate'}
                onClick={async () => {
                  setBusy('rotate');
                  try {
                    await axios.patch(`/api/integrations/${selected.id}`, {
                      api_token: form.api_token.trim(),
                      auth_email: form.auth_email || selected.auth_email
                    });
                    const res = await axios.post(`/api/integrations/${selected.id}/test`);
                    showMessage(res.data.error ? 'error' : 'success', res.data.error || 'API key updated.');
                    setForm(emptyForm(kind));
                    await loadConnections();
                  } catch (error) {
                    showMessage('error', error.response?.data?.error || 'Failed to update API key.');
                  } finally {
                    setBusy('');
                  }
                }}
              >
                {busy === 'rotate' ? 'Updating…' : 'Update key'}
              </Button>
              <Button size="small" onClick={handleTest} disabled={busy === 'test'}>
                {busy === 'test' ? 'Testing…' : 'Test connection'}
              </Button>
              <Button size="small" onClick={handleDelete} disabled={busy === 'delete'}>
                Disconnect
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div style={{ ...FORM_GRID, marginTop: SPACE.x16 }}>
              <Field
                label="Display name"
                value={form.name}
                onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
                placeholder={metaCopy.label}
              />
              <Field
                label={`${metaCopy.label} URL`}
                value={form.base_url}
                onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))}
                placeholder={kind === 'jira' ? 'https://your-site.atlassian.net' : 'https://dojo.example.com'}
              />
              {kind === 'jira' ? (
                <>
                  <Combo
                    label="Auth"
                    options={[
                      { value: 'api_token', label: 'Cloud email + API token' },
                      { value: 'pat', label: 'Data Center personal access token' }
                    ]}
                    value={form.auth_type}
                    onChange={(value) => setForm((prev) => ({ ...prev, auth_type: value }))}
                  />
                  {form.auth_type !== 'pat' ? (
                    <Field
                      label="Jira email"
                      value={form.auth_email}
                      onChange={(event) => setForm((prev) => ({ ...prev, auth_email: event.target.value }))}
                      placeholder="you@company.com"
                    />
                  ) : null}
                </>
              ) : null}
              <Field
                label={kind === 'jira' ? 'API token' : 'API key'}
                type="password"
                value={form.api_token}
                onChange={(event) => setForm((prev) => ({ ...prev, api_token: event.target.value }))}
                autoComplete="new-password"
              />
            </div>
            <div style={{ ...ACTIONS, marginTop: SPACE.x16 }}>
              <Button variant="contained" size="small" onClick={handleConnect} disabled={saving}>
                {saving ? 'Connecting…' : `Connect ${metaCopy.label}`}
              </Button>
            </div>
          </>
        )}
      </Surface>

      {selected && selected.status === 'connected' ? (
        <Surface style={{ padding: SPACE.x24 }}>
          <Text as="h2" variant="h2" style={{ margin: 0 }}>
            {kind === 'jira' ? 'Ticket template' : 'Product mapping'}
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: '8px 0 16px' }}>
            {kind === 'jira'
              ? 'Pick the Jira project and issue type testers will file into. RAPTOR reads that screen’s fields so you can map or expose them.'
              : 'Pick the DefectDojo product. Engagements can be created per wave so each engagement stays tidy.'}
          </Text>

          {templates.length > 1 ? (
            <div style={{ marginBottom: SPACE.x16 }}>
              <Combo
                label="Saved templates"
                options={templates.map((item) => ({
                  value: String(item.id),
                  label: `${item.name}${item.is_default ? ' (default)' : ''}`
                }))}
                value={selectedTemplate ? String(selectedTemplate.id) : ''}
                onChange={(value) => setSelectedTemplateId(Number(value))}
              />
            </div>
          ) : null}

          <div style={FORM_GRID}>
            <Field
              label="Template name"
              value={draft.name}
              onChange={(event) => setDraft((prev) => ({ ...prev, name: event.target.value }))}
              placeholder={kind === 'jira' ? 'SEC / Bug' : 'Payments product'}
            />
            {kind === 'jira' ? (
              <>
                <Combo
                  label={metaCopy.projectLabel}
                  placeholder={catalog.projects.length ? 'Select a project' : 'No projects yet'}
                  hint={catalog.projects.length ? undefined : 'Test the connection if this stays empty.'}
                  options={catalog.projects.map((item) => ({ value: item.key, label: `${item.name} (${item.key})` }))}
                  value={draft.project}
                  onChange={(value) => setDraft((prev) => ({ ...prev, project: value, issueType: '' }))}
                />
                <Combo
                  label={metaCopy.typeLabel}
                  placeholder={draft.project ? 'Select an issue type' : 'Choose a project first'}
                  options={catalog.issueTypes.map((item) => ({ value: item.id, label: item.name }))}
                  value={draft.issueType}
                  onChange={(value) => setDraft((prev) => ({ ...prev, issueType: value }))}
                  disabled={!draft.project}
                />
              </>
            ) : (
              <>
                <Combo
                  label={metaCopy.projectLabel}
                  placeholder="Select a product"
                  options={catalog.products.map((item) => ({ value: String(item.id), label: item.name }))}
                  value={String(draft.product || '')}
                  onChange={(value) => setDraft((prev) => ({ ...prev, product: value }))}
                />
                <Combo
                  label="Engagement"
                  options={ENGAGEMENT_MODES}
                  value={draft.engagementMode}
                  onChange={(value) => setDraft((prev) => ({ ...prev, engagementMode: value }))}
                />
                {draft.engagementMode === 'fixed' ? (
                  <Combo
                    label="Fixed engagement"
                    placeholder="Select an engagement"
                    options={catalog.engagements.map((item) => ({ value: String(item.id), label: item.name }))}
                    value={String(draft.engagementId || '')}
                    onChange={(value) => setDraft((prev) => ({ ...prev, engagementId: value }))}
                  />
                ) : null}
                <Combo
                  label="Test"
                  options={TEST_MODES}
                  value={draft.testMode}
                  onChange={(value) => setDraft((prev) => ({ ...prev, testMode: value }))}
                />
              </>
            )}
          </div>
          <div style={{ ...ACTIONS, marginTop: SPACE.x16 }}>
            <Button variant="contained" size="small" onClick={handleCreateTemplate} disabled={busy === 'template'}>
              {selectedTemplate ? 'Save as new template' : `Create ${metaCopy.templateNoun}`}
            </Button>
            {selectedTemplate && !selectedTemplate.is_default ? (
              <Button size="small" onClick={() => handleSetDefault(selectedTemplate)}>
                Make default
              </Button>
            ) : null}
          </div>
        </Surface>
      ) : null}

      {selectedTemplate ? (
        <Surface style={{ padding: SPACE.x24 }}>
          <Text as="h2" variant="h2" style={{ margin: '0 0 16px' }}>
            Field mapping
          </Text>
          <FieldMappingEditor
            mappings={mappings}
            raptorFields={meta.raptor_fields || []}
            kind={kind}
            onChange={setMappings}
            onRefresh={handleRefreshFields}
            refreshing={busy === 'refresh'}
            saving={busy === 'map'}
            onSave={handleSaveMappings}
          />
        </Surface>
      ) : selected && selected.status === 'connected' ? (
        <EmptyState
          icon={Hub}
          title={`No ${metaCopy.templateNoun} yet`}
          hint={
            kind === 'jira'
              ? 'Choose a project and issue type, then map RAPTOR fields onto that screen.'
              : 'Choose a product so testers can push findings into DefectDojo.'
          }
        />
      ) : null}
    </div>
  );
};

export default IntegrationsSection;
