import React, { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import {
  Button,
  Combo,
  DataList,
  DataRow,
  EmptyState,
  Field,
  Panel,
  ProviderMark,
  RefreshButton,
  SwitchRow,
  Tag,
  Text
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import SectionHeader from './SectionHeader';

const emptyForm = {
  type: 'anthropic',
  display_name: '',
  api_key: '',
  base_url: '',
  endpoint: '',
  region: 'us-chicago-1',
  aws_region: 'us-east-1',
  access_key_id: '',
  aws_secret_access_key: '',
  aws_bearer_token: '',
  aws_session_token: '',
  api_version: '2024-10-21',
  project_ocid: '',
  extra_headers: '',
  models: []
};

const activeKey = (connectionId, modelId) => `${connectionId}::${modelId}`;

const AiConnectionsPanel = ({ showMessage }) => {
  const [config, setConfig] = useState({});
  const [connections, setConnections] = useState([]);
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [manualModel, setManualModel] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cfgRes, connRes, provRes] = await Promise.all([
        axios.get('/admin/scanner-config'),
        axios.get('/admin/llm/connections'),
        axios.get('/admin/llm/providers')
      ]);
      setConfig(cfgRes.data?.config || {});
      setConnections(connRes.data?.connections || []);
      setProviders(provRes.data?.providers || []);
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to load AI connections.');
    } finally {
      setLoading(false);
    }
  }, [showMessage]);

  useEffect(() => {
    load();
  }, [load]);

  const typeOptions = useMemo(
    () => providers.map((item) => ({ value: item.type, label: item.label })),
    [providers]
  );

  const modelOptions = useMemo(() => {
    const options = [];
    connections.forEach((connection) => {
      (connection.models || [])
        .filter((model) => model.selected !== false)
        .forEach((model) => {
          options.push({
            value: activeKey(connection.id, model.id),
            label: `${connection.display_name} · ${model.display_name || model.id}`
          });
        });
    });
    return options;
  }, [connections]);

  const savePolicy = async (patch) => {
    try {
      await axios.put('/admin/scanner-config', patch);
      await load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to update scanner policy.');
    }
  };

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setManualModel('');
    setDialogOpen(true);
  };

  const openEdit = (connection) => {
    const cfg = connection.config || {};
    setEditing(connection);
    setForm({
      ...emptyForm,
      type: connection.type,
      display_name: connection.display_name || '',
      api_key: '',
      base_url: cfg.base_url || '',
      endpoint: cfg.endpoint || '',
      region: cfg.region || 'us-chicago-1',
      aws_region: cfg.aws_region || 'us-east-1',
      access_key_id: cfg.access_key_id || '',
      aws_secret_access_key: '',
      aws_bearer_token: '',
      aws_session_token: '',
      api_version: cfg.api_version || '2024-10-21',
      project_ocid: cfg.project_ocid || '',
      extra_headers: cfg.extra_headers ? JSON.stringify(cfg.extra_headers, null, 2) : '',
      models: connection.models || []
    });
    setManualModel('');
    setDialogOpen(true);
  };

  const configFromForm = () => {
    const config = {};
    const assign = (key, value) => {
      if (value !== undefined && value !== '') config[key] = value;
    };
    assign('api_key', form.api_key);
    assign('base_url', form.base_url);
    assign('endpoint', form.endpoint);
    assign('region', form.region);
    assign('aws_region', form.aws_region);
    assign('access_key_id', form.access_key_id);
    assign('aws_secret_access_key', form.aws_secret_access_key);
    assign('aws_bearer_token', form.aws_bearer_token);
    assign('aws_session_token', form.aws_session_token);
    assign('api_version', form.api_version);
    assign('project_ocid', form.project_ocid);
    if (form.extra_headers.trim()) {
      try {
        config.extra_headers = JSON.parse(form.extra_headers);
      } catch {
        config.extra_headers = {};
      }
    }
    return config;
  };

  const save = async () => {
    try {
      const body = {
        type: form.type,
        display_name: form.display_name,
        config: configFromForm(),
        models: form.models
      };
      if (editing) {
        await axios.patch(`/admin/llm/connections/${editing.id}`, body);
        showMessage?.('success', 'Connection updated.');
      } else {
        await axios.post('/admin/llm/connections', body);
        showMessage?.('success', 'Connection created.');
      }
      setDialogOpen(false);
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to save connection.');
    }
  };

  const toggleEnabled = async (connection) => {
    if (connection.type === 'local') return;
    try {
      await axios.patch(`/admin/llm/connections/${connection.id}`, { enabled: !connection.enabled });
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to update connection.');
    }
  };

  const refreshModels = async (connection) => {
    try {
      await axios.post(`/admin/llm/connections/${connection.id}/refresh-models`);
      showMessage?.('success', 'Model catalog refreshed.');
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to refresh models.');
      load();
    }
  };

  const testConnection = async (connection) => {
    try {
      const response = await axios.post(`/admin/llm/connections/${connection.id}/test`);
      showMessage?.(response.data?.ok ? 'success' : 'error', response.data?.message || 'Test finished.');
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || error.response?.data?.message || 'Test failed.');
      load();
    }
  };

  const remove = async (connection) => {
    try {
      await axios.delete(`/admin/llm/connections/${connection.id}`);
      showMessage?.('success', 'Connection removed.');
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to delete connection.');
    }
  };

  const toggleModel = (modelId) => {
    setForm((prev) => ({
      ...prev,
      models: (prev.models || []).map((model) =>
        model.id === modelId ? { ...model, selected: !model.selected } : model
      )
    }));
  };

  const addManualModel = () => {
    const id = manualModel.trim();
    if (!id) return;
    setForm((prev) => {
      if ((prev.models || []).some((model) => model.id === id)) return prev;
      return {
        ...prev,
        models: [...(prev.models || []), { id, display_name: id, source: 'manual', selected: true, tools: true }]
      };
    });
    setManualModel('');
  };

  const suggested = providers.find((item) => item.type === form.type)?.suggested_models || [];

  return (
    <div>
      <SectionHeader title="Connections">
        <Button variant="contained" size="small" onClick={openCreate}>
          Add provider
        </Button>
      </SectionHeader>
      <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x16}px`, maxWidth: 640 }}>
        Save API providers here, pick which models to use, then choose the active scan model.
        Install RAPTOR Local if you do not want a hosted API.
      </Text>
      <SwitchRow
        label="Enable AI scanner"
        hint="Launches from an open, started wave or the live scan console use the active model."
        checked={Boolean(Number(config.enabled || 0))}
        onChange={(checked) => savePolicy({ enabled: checked })}
      />
      <div style={{ maxWidth: 480, marginBottom: SPACE.x24 }}>
        <Combo
          label="Active scan model"
          options={modelOptions}
          value={
            config.active_connection_id && config.active_model_id
              ? activeKey(config.active_connection_id, config.active_model_id)
              : ''
          }
          onChange={(next) => {
            if (!next) {
              savePolicy({ active_connection_id: null, active_model_id: '' });
              return;
            }
            const [connectionId, ...rest] = String(next).split('::');
            savePolicy({ active_connection_id: Number(connectionId), active_model_id: rest.join('::') });
          }}
        />
      </div>
      {loading && connections.length === 0 ? (
        <Text variant="meta" tone="secondary">
          Loading connections…
        </Text>
      ) : null}
      {!loading && connections.length === 0 ? (
        <EmptyState title="Install RAPTOR Local, or add Anthropic / OpenAI / Gemini / …" />
      ) : (
        <DataList>
          {connections.map((connection) => (
            <DataRow
              key={connection.id}
              id={connection.id}
              leading={<ProviderMark type={connection.type} size={20} />}
              title={<Text variant="bodyStrong">{connection.display_name}</Text>}
              meta={
                <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 2 }}>
                  {(connection.models || []).filter((model) => model.selected !== false).length} models
                  {connection.last_error ? ` · ${connection.last_error}` : ''}
                </Text>
              }
              trailing={
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8, flexWrap: 'wrap' }}
                  onClick={(event) => event.stopPropagation()}
                >
                  <Tag>{connection.type_label || connection.type}</Tag>
                  <Tag>{connection.enabled ? 'Enabled' : 'Disabled'}</Tag>
                  {connection.type !== 'local' ? (
                    <>
                      <Button size="small" onClick={() => testConnection(connection)}>
                        Test
                      </Button>
                      <RefreshButton onClick={() => refreshModels(connection)}>
                        Refresh models
                      </RefreshButton>
                      <Button size="small" onClick={() => openEdit(connection)}>
                        Edit
                      </Button>
                      <Button size="small" onClick={() => toggleEnabled(connection)}>
                        {connection.enabled ? 'Disable' : 'Enable'}
                      </Button>
                      <Button size="small" onClick={() => remove(connection)}>
                        Delete
                      </Button>
                    </>
                  ) : (
                    <Tag>Built-in</Tag>
                  )}
                </div>
              }
            />
          ))}
        </DataList>
      )}

      <Panel
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editing ? 'Edit connection' : 'Add provider'}
        actions={
          <>
            <Button onClick={() => setDialogOpen(false)} variant="outlined">
              Cancel
            </Button>
            <Button variant="contained" onClick={save}>
              Save
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8 }}>
          <ProviderMark type={form.type} size={22} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <Combo
              label="Provider"
              options={typeOptions}
              value={form.type}
              onChange={(next) => next && setForm((prev) => ({ ...prev, type: next }))}
              disableClearable
              disabled={Boolean(editing)}
            />
          </div>
        </div>
        <Field
          label="Display name"
          value={form.display_name}
          onChange={(event) => setForm((prev) => ({ ...prev, display_name: event.target.value }))}
        />
        {['anthropic', 'openai', 'gemini', 'kimi', 'qwen', 'deepseek', 'openai_compat', 'anthropic_compat', 'azure', 'oracle'].includes(
          form.type
        ) ? (
          <Field
            label={editing ? 'API key (leave blank to keep)' : 'API key'}
            type="password"
            value={form.api_key}
            onChange={(event) => setForm((prev) => ({ ...prev, api_key: event.target.value }))}
          />
        ) : null}
        {['kimi', 'qwen', 'openai_compat', 'anthropic_compat'].includes(form.type) ? (
          <Field
            label="Base URL"
            value={form.base_url}
            onChange={(event) => setForm((prev) => ({ ...prev, base_url: event.target.value }))}
          />
        ) : null}
        {form.type === 'azure' ? (
          <>
            <Field
              label="Endpoint"
              value={form.endpoint}
              onChange={(event) => setForm((prev) => ({ ...prev, endpoint: event.target.value }))}
            />
            <Field
              label="API version"
              value={form.api_version}
              onChange={(event) => setForm((prev) => ({ ...prev, api_version: event.target.value }))}
            />
          </>
        ) : null}
        {form.type === 'oracle' ? (
          <>
            <Field
              label="Region"
              value={form.region}
              onChange={(event) => setForm((prev) => ({ ...prev, region: event.target.value }))}
            />
            <Field
              label="Project OCID (optional)"
              value={form.project_ocid}
              onChange={(event) => setForm((prev) => ({ ...prev, project_ocid: event.target.value }))}
            />
          </>
        ) : null}
        {form.type === 'bedrock' ? (
          <>
            <Field
              label="AWS region"
              value={form.aws_region}
              onChange={(event) => setForm((prev) => ({ ...prev, aws_region: event.target.value }))}
            />
            <Field
              label={editing ? 'Bearer token (leave blank to keep)' : 'Bearer token'}
              type="password"
              value={form.aws_bearer_token}
              onChange={(event) => setForm((prev) => ({ ...prev, aws_bearer_token: event.target.value }))}
            />
            <Field
              label="Access key ID"
              value={form.access_key_id}
              onChange={(event) => setForm((prev) => ({ ...prev, access_key_id: event.target.value }))}
            />
            <Field
              label={editing ? 'Secret access key (leave blank to keep)' : 'Secret access key'}
              type="password"
              value={form.aws_secret_access_key}
              onChange={(event) => setForm((prev) => ({ ...prev, aws_secret_access_key: event.target.value }))}
            />
          </>
        ) : null}
        {['openai_compat', 'anthropic_compat'].includes(form.type) ? (
          <Field
            label="Extra headers JSON (optional)"
            value={form.extra_headers}
            onChange={(event) => setForm((prev) => ({ ...prev, extra_headers: event.target.value }))}
            multiline
            minRows={3}
          />
        ) : null}
        <Text as="div" variant="micro" tone="tertiary" style={{ marginTop: SPACE.x8 }}>
          Models
        </Text>
        {(form.models || []).length === 0 ? (
          <Text variant="meta" tone="secondary">
            Save, then Refresh models — or add an id manually.
            {suggested.length ? ` Suggested: ${suggested.map((item) => item.id).join(', ')}` : ''}
          </Text>
        ) : (
          (form.models || []).map((model) => (
            <div key={model.id} style={{ display: 'flex', justifyContent: 'space-between', gap: SPACE.x8 }}>
              <Text variant="meta">{model.display_name || model.id}</Text>
              <Button size="small" onClick={() => toggleModel(model.id)}>
                {model.selected === false ? 'Include' : 'Selected'}
              </Button>
            </div>
          ))
        )}
        <div style={{ display: 'flex', gap: SPACE.x8, alignItems: 'flex-end' }}>
          <div style={{ flex: 1 }}>
            <Field
              label="Add model id"
              value={manualModel}
              onChange={(event) => setManualModel(event.target.value)}
            />
          </div>
          <Button size="small" onClick={addManualModel}>
            Add
          </Button>
        </div>
      </Panel>
    </div>
  );
};

export default AiConnectionsPanel;
