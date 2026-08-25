import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Button,
  Combo,
  DataList,
  DataRow,
  EmptyState,
  Field,
  Mono,
  Panel,
  ProviderMark,
  Tag,
  Text
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import SectionHeader from './SectionHeader';

const TYPE_OPTIONS = [
  { value: 'cloudflare', label: 'Cloudflare' },
  { value: 'route53', label: 'Amazon Route 53' },
  { value: 'alidns', label: 'Alibaba Cloud DNS' },
  { value: 'azure', label: 'Azure DNS' },
  { value: 'gcp', label: 'Google Cloud DNS' }
];

const emptyForm = {
  type: 'cloudflare',
  display_name: '',
  api_token: '',
  access_key_id: '',
  aws_secret_access_key: '',
  access_key_secret: '',
  region: 'us-east-1',
  role_arn: '',
  tenant_id: '',
  client_id: '',
  client_secret: '',
  subscription_id: '',
  project_id: '',
  service_account_json: '',
  zone_allowlist: '',
  interval_seconds: '3600'
};

const formatWhen = (value) => {
  if (!value) return 'never';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
};

const CloudDnsSection = ({ showMessage }) => {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [zones, setZones] = useState([]);
  const [zonesFor, setZonesFor] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get('/admin/dns-sources');
      setSources(response.data?.sources || []);
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to load cloud DNS connectors.');
    } finally {
      setLoading(false);
    }
  }, [showMessage]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (source) => {
    const config = source.config || {};
    setEditing(source);
    setForm({
      type: source.type,
      display_name: source.display_name || '',
      api_token: '',
      access_key_id: config.access_key_id || '',
      aws_secret_access_key: '',
      access_key_secret: '',
      region: config.region || 'us-east-1',
      role_arn: config.role_arn || '',
      tenant_id: config.tenant_id || '',
      client_id: config.client_id || '',
      client_secret: '',
      subscription_id: config.subscription_id || '',
      project_id: config.project_id || '',
      service_account_json: '',
      zone_allowlist: (config.zone_allowlist || []).join('\n'),
      interval_seconds: String(config.interval_seconds || 3600)
    });
    setDialogOpen(true);
  };

  const configFromForm = () => {
    const config = {
      zone_allowlist: form.zone_allowlist,
      interval_seconds: form.interval_seconds
    };
    if (form.type === 'cloudflare') {
      config.api_token = form.api_token;
    } else if (form.type === 'route53') {
      config.access_key_id = form.access_key_id;
      config.aws_secret_access_key = form.aws_secret_access_key;
      config.region = form.region;
      config.role_arn = form.role_arn;
    } else if (form.type === 'alidns') {
      config.access_key_id = form.access_key_id;
      config.access_key_secret = form.access_key_secret;
    } else if (form.type === 'azure') {
      config.tenant_id = form.tenant_id;
      config.client_id = form.client_id;
      config.client_secret = form.client_secret;
      config.subscription_id = form.subscription_id;
    } else if (form.type === 'gcp') {
      config.project_id = form.project_id;
      config.service_account_json = form.service_account_json;
    }
    return config;
  };

  const save = async () => {
    try {
      if (editing) {
        await axios.patch(`/admin/dns-sources/${editing.id}`, {
          display_name: form.display_name,
          config: configFromForm()
        });
        showMessage?.('success', 'Connector updated.');
      } else {
        await axios.post('/admin/dns-sources', {
          type: form.type,
          display_name: form.display_name,
          config: configFromForm()
        });
        showMessage?.('success', 'Connector created.');
      }
      setDialogOpen(false);
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to save connector.');
    }
  };

  const syncNow = async (source) => {
    try {
      await axios.post(`/admin/dns-sources/${source.id}/sync-now`);
      showMessage?.('success', `Sync queued for ${source.display_name}.`);
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to queue sync.');
    }
  };

  const toggleEnabled = async (source) => {
    const enabling = !source.enabled;
    try {
      await axios.patch(`/admin/dns-sources/${source.id}`, { enabled: enabling });
      showMessage?.(
        'success',
        enabling
          ? `${source.display_name} enabled.`
          : `${source.display_name} disabled. Hosts and observations were kept.`
      );
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to update connector.');
    }
  };

  const remove = async (source) => {
    try {
      const response = await axios.delete(`/admin/dns-sources/${source.id}`);
      showMessage?.(
        'success',
        response.data?.message || `${source.display_name} deleted. Hosts and observations were kept.`
      );
      setPendingDelete(null);
      load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to delete connector.');
    }
  };

  const loadZones = async (source) => {
    try {
      const response = await axios.get(`/admin/dns-sources/${source.id}/zones`);
      setZones(response.data?.zones || []);
      setZonesFor(source);
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Failed to load zones.');
    }
  };

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));

  return (
    <div>
      <SectionHeader title="Cloud DNS">
        <Button variant="contained" size="small" onClick={openCreate}>
          Add connector
        </Button>
      </SectionHeader>
      {loading && sources.length === 0 ? (
        <Text variant="meta" tone="secondary">
          Loading connectors…
        </Text>
      ) : null}
      {!loading && sources.length === 0 ? (
        <EmptyState title="No cloud DNS connectors yet" />
      ) : (
        <DataList>
          {sources.map((source) => (
            <DataRow
              key={source.id}
              id={source.id}
              leading={<ProviderMark type={source.type} size={20} />}
              title={<Text variant="bodyStrong">{source.display_name}</Text>}
              meta={
                <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 2 }}>
                  Last success {formatWhen(source.last_success_at)}
                  {source.last_error ? ` · ${source.last_error}` : ''}
                </Text>
              }
              trailing={
                <div
                  style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8, flexWrap: 'wrap' }}
                  onClick={(event) => event.stopPropagation()}
                >
                  <Tag>{source.type_label || source.type}</Tag>
                  <Tag>{source.enabled ? 'Enabled' : 'Disabled'}</Tag>
                  <Tag>{`${source.zone_count || 0} zones`}</Tag>
                  <Button size="small" variant="contained" onClick={() => syncNow(source)}>
                    Sync now
                  </Button>
                  <Button size="small" variant="outlined" onClick={() => loadZones(source)}>
                    Zones
                  </Button>
                  <Button size="small" variant="outlined" color="primary" onClick={() => openEdit(source)}>
                    Edit
                  </Button>
                  {source.enabled ? (
                    <Button size="small" variant="outlined" onClick={() => toggleEnabled(source)}>
                      Disable
                    </Button>
                  ) : (
                    <Button size="small" variant="contained" onClick={() => toggleEnabled(source)}>
                      Enable
                    </Button>
                  )}
                  <Button size="small" variant="outlined" color="error" onClick={() => setPendingDelete(source)}>
                    Delete
                  </Button>
                </div>
              }
            />
          ))}
        </DataList>
      )}

      <Panel
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title={editing ? 'Edit connector' : 'Add cloud DNS connector'}
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
              options={TYPE_OPTIONS}
              value={form.type}
              onChange={(next) => next && update('type', next)}
              disableClearable
              disabled={Boolean(editing)}
            />
          </div>
        </div>
        <Field
          label="Display name"
          value={form.display_name}
          onChange={(event) => update('display_name', event.target.value)}
        />
        {form.type === 'cloudflare' ? (
          <>
            <Field
              label={editing ? 'API token (leave blank to keep)' : 'API token'}
              type="password"
              value={form.api_token}
              onChange={(event) => update('api_token', event.target.value)}
            />
          </>
        ) : null}
        {form.type === 'route53' ? (
          <>
            <Field
              label="Access key ID"
              value={form.access_key_id}
              onChange={(event) => update('access_key_id', event.target.value)}
            />
            <Field
              label={editing ? 'Secret access key (leave blank to keep)' : 'Secret access key'}
              type="password"
              value={form.aws_secret_access_key}
              onChange={(event) => update('aws_secret_access_key', event.target.value)}
            />
            <Field
              label="Region"
              value={form.region}
              onChange={(event) => update('region', event.target.value)}
            />
            <Field
              label="Assume role ARN (optional)"
              value={form.role_arn}
              onChange={(event) => update('role_arn', event.target.value)}
            />
          </>
        ) : null}
        {form.type === 'alidns' ? (
          <>
            <Field
              label="AccessKey ID"
              value={form.access_key_id}
              onChange={(event) => update('access_key_id', event.target.value)}
            />
            <Field
              label={editing ? 'AccessKey secret (leave blank to keep)' : 'AccessKey secret'}
              type="password"
              value={form.access_key_secret}
              onChange={(event) => update('access_key_secret', event.target.value)}
            />
          </>
        ) : null}
        {form.type === 'azure' ? (
          <>
            <Field
              label="Tenant ID"
              value={form.tenant_id}
              onChange={(event) => update('tenant_id', event.target.value)}
            />
            <Field
              label="Application (client) ID"
              value={form.client_id}
              onChange={(event) => update('client_id', event.target.value)}
            />
            <Field
              label={editing ? 'Client secret (leave blank to keep)' : 'Client secret'}
              type="password"
              value={form.client_secret}
              onChange={(event) => update('client_secret', event.target.value)}
            />
            <Field
              label="Subscription ID"
              value={form.subscription_id}
              onChange={(event) => update('subscription_id', event.target.value)}
            />
          </>
        ) : null}
        {form.type === 'gcp' ? (
          <>
            <Field
              label="Project ID"
              value={form.project_id}
              onChange={(event) => update('project_id', event.target.value)}
            />
            <Field
              label={editing ? 'Service account JSON (leave blank to keep)' : 'Service account JSON'}
              value={form.service_account_json}
              onChange={(event) => update('service_account_json', event.target.value)}
              multiline
              minRows={6}
            />
          </>
        ) : null}
        <Field
          label="Zone allowlist (optional, one per line)"
          value={form.zone_allowlist}
          onChange={(event) => update('zone_allowlist', event.target.value)}
          multiline
          minRows={3}
        />
        <Field
          label="Interval seconds"
          value={form.interval_seconds}
          onChange={(event) => update('interval_seconds', event.target.value)}
        />
      </Panel>

      <Panel
        open={Boolean(zonesFor)}
        onClose={() => setZonesFor(null)}
        title={zonesFor ? `Zones · ${zonesFor.display_name}` : 'Zones'}
        actions={
          <Button onClick={() => setZonesFor(null)} variant="outlined">
            Close
          </Button>
        }
      >
        {zones.length === 0 ? (
          <Text variant="meta" tone="secondary">
            No zones in the latest ingest yet. Run Sync now.
          </Text>
        ) : (
          zones.map((zone) => (
            <div key={`${zone.zone}-${zone.provider_zone_id}`}>
              <Mono>
                {zone.zone}
                {zone.record_count ? ` (${zone.record_count})` : ''}
              </Mono>
            </div>
          ))
        )}
      </Panel>

      <Panel
        open={Boolean(pendingDelete)}
        onClose={() => setPendingDelete(null)}
        title="Delete connector"
        actions={
          <>
            <Button onClick={() => setPendingDelete(null)} variant="outlined">
              Cancel
            </Button>
            <Button variant="contained" color="error" onClick={() => pendingDelete && remove(pendingDelete)}>
              Delete
            </Button>
          </>
        }
      >
        <Text variant="body">
          Delete {pendingDelete?.display_name}? RAPTOR will drop this connector and its secrets. Hosts
          and DNS observations stay.
        </Text>
      </Panel>
    </div>
  );
};

export default CloudDnsSection;
