import axios from 'axios';
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Combo,
  EmptyState,
  Field,
  Mono,
  Surface,
  SwitchRow,
  Text
} from '../../../../design/primitives';
import { SPACE } from '../../../../design/tokens';
import { ROLE_OPTIONS } from '../../constants';
import AuthTypeChip from '../AuthTypeChip';
import SectionHeader from '../SectionHeader';

const EMPTY_FORM = {
  alias: '',
  display_name: '',
  protocol: 'oidc',
  enabled: true,
  client_id: '',
  client_secret: '',
  issuer: '',
  authorization_url: '',
  token_url: '',
  jwks_url: '',
  logout_url: '',
  entity_id: '',
  sso_url: '',
  metadata_url: ''
};

const PROTOCOL_OPTIONS = [
  { value: 'oidc', label: 'OIDC' },
  { value: 'saml', label: 'SAML' }
];

const SsoConnectionsPanel = ({ showMessage }) => {
  const [connections, setConnections] = useState([]);
  const [redirectUri, setRedirectUri] = useState('');
  const [selectedAlias, setSelectedAlias] = useState('');
  const [form, setForm] = useState(EMPTY_FORM);
  const [creating, setCreating] = useState(true);
  const [loading, setLoading] = useState(false);
  const [allowUsername, setAllowUsername] = useState('');
  const [allowEmail, setAllowEmail] = useState('');
  const [allowRole, setAllowRole] = useState('user');
  const [allowProtocol, setAllowProtocol] = useState('oidc');

  const selected = useMemo(
    () => connections.find((row) => row.alias === selectedAlias) || null,
    [connections, selectedAlias]
  );

  const load = useCallback(async () => {
    const response = await axios.get('/sso/connections');
    const rows = response.data?.connections || [];
    setConnections(rows);
    setRedirectUri(response.data?.redirect_uri || '');
    return rows;
  }, []);

  useEffect(() => {
    load().catch(() => {
      showMessage?.('error', 'Could not load SSO connections.');
    });
  }, [load, showMessage]);

  const updateField = (key, value) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const startCreate = () => {
    setCreating(true);
    setSelectedAlias('');
    setForm(EMPTY_FORM);
  };

  const selectConnection = (row) => {
    setCreating(false);
    setSelectedAlias(row.alias);
    setForm({
      ...EMPTY_FORM,
      alias: row.alias,
      display_name: row.display_name || row.alias,
      protocol: row.protocol || 'oidc',
      enabled: Boolean(row.enabled),
      client_id: row.client_id || '',
      issuer: row.issuer || '',
      authorization_url: row.authorization_url || '',
      token_url: row.token_url || '',
      jwks_url: row.jwks_url || '',
      logout_url: row.logout_url || '',
      entity_id: row.entity_id || '',
      sso_url: row.sso_url || '',
      metadata_url: row.metadata_url || ''
    });
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      if (creating) {
        await axios.post('/sso/connections', form);
        showMessage?.('success', 'SSO connection created.');
      } else {
        const payload = { ...form };
        if (!payload.client_secret) delete payload.client_secret;
        await axios.put(`/sso/connections/${encodeURIComponent(selectedAlias)}`, payload);
        showMessage?.('success', 'SSO connection saved.');
      }
      const rows = await load();
      if (creating && form.alias) {
        const created = rows.find((row) => row.alias === form.alias);
        if (created) selectConnection(created);
      }
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Could not save SSO connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleTest = async () => {
    if (!selectedAlias) return;
    setLoading(true);
    try {
      const response = await axios.post(`/sso/connections/${encodeURIComponent(selectedAlias)}/test`);
      showMessage?.('success', response.data?.message || 'Connection test succeeded.');
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Connection test failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedAlias) return;
    setLoading(true);
    try {
      await axios.delete(`/sso/connections/${encodeURIComponent(selectedAlias)}`);
      showMessage?.('success', 'SSO connection deleted.');
      startCreate();
      await load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Could not delete SSO connection.');
    } finally {
      setLoading(false);
    }
  };

  const handleAllowlist = async () => {
    setLoading(true);
    try {
      await axios.post('/sso/allowlist', {
        username: allowUsername,
        email: allowEmail,
        role: allowRole,
        auth_type: allowProtocol
      });
      showMessage?.('success', `Allowlisted ${allowUsername} for ${allowProtocol.toUpperCase()} sign-in.`);
      setAllowUsername('');
      setAllowEmail('');
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Could not allowlist user.');
    } finally {
      setLoading(false);
    }
  };

  const protocol = form.protocol || 'oidc';

  return (
    <div>
      <SectionHeader title="Sign-in / SSO" />
      <Text as="p" variant="meta" tone="secondary" style={{ marginTop: 0, marginBottom: SPACE.x16 }}>
        OIDC and SAML only. Other Keycloak identity providers are ignored. Users still need an allowlist
        row before they can sign in.
      </Text>
      <div className="raptor-users-split">
        <Surface className="raptor-users-pane" style={{ padding: SPACE.x16, gap: SPACE.x16 }}>
          <Text variant="bodyStrong">Connections</Text>
          {connections.length === 0 ? (
            <EmptyState title="No SSO connections" hint="Create an OIDC or SAML connection on the right." />
          ) : (
            connections.map((row) => (
              <button
                key={row.alias}
                type="button"
                onClick={() => selectConnection(row)}
                className="raptor-users-card"
                style={{
                  textAlign: 'left',
                  cursor: 'pointer',
                  border: selectedAlias === row.alias ? '1px solid var(--raptor-users-accent)' : '1px solid transparent'
                }}
              >
                <div className="raptor-users-card-row">
                  <Text className="raptor-users-card-name" variant="bodyStrong">
                    {row.display_name || row.alias}
                  </Text>
                  <AuthTypeChip authType={row.protocol} />
                </div>
                <div className="raptor-users-card-meta">
                  <Text variant="micro" tone="tertiary">
                    {row.enabled ? 'Enabled' : 'Disabled'} · {row.alias}
                  </Text>
                </div>
              </button>
            ))
          )}
          <div className="raptor-users-pane-foot">
            <Button variant="outlined" onClick={startCreate} style={{ width: '100%' }}>
              New connection
            </Button>
          </div>
        </Surface>

        <Surface className="raptor-users-pane" style={{ padding: SPACE.x16, gap: SPACE.x16 }}>
          <Text variant="bodyStrong">{creating ? 'Create connection' : 'Edit connection'}</Text>
          <Combo
            label="Protocol"
            options={PROTOCOL_OPTIONS}
            value={protocol}
            onChange={(value) => updateField('protocol', value || 'oidc')}
            disabled={!creating}
            disableClearable
          />
          <Field
            label="Alias"
            value={form.alias}
            onChange={(event) => updateField('alias', event.target.value)}
            placeholder="corp-oidc"
            disabled={!creating}
          />
          <Field
            label="Display name"
            value={form.display_name}
            onChange={(event) => updateField('display_name', event.target.value)}
            placeholder="Corporate SSO"
          />
          <SwitchRow
            label="Enabled"
            checked={Boolean(form.enabled)}
            onChange={(checked) => updateField('enabled', checked)}
          />
          {protocol === 'oidc' ? (
            <>
              <Field
                label="Issuer"
                value={form.issuer}
                onChange={(event) => updateField('issuer', event.target.value)}
                placeholder="https://idp.example.com/realms/corp"
              />
              <Field
                label="Client ID"
                value={form.client_id}
                onChange={(event) => updateField('client_id', event.target.value)}
              />
              <Field
                label="Client secret"
                type="password"
                value={form.client_secret}
                onChange={(event) => updateField('client_secret', event.target.value)}
                placeholder={creating ? '' : 'Leave blank to keep'}
              />
              <Field
                label="Authorization URL (optional)"
                value={form.authorization_url}
                onChange={(event) => updateField('authorization_url', event.target.value)}
              />
              <Field
                label="Token URL (optional)"
                value={form.token_url}
                onChange={(event) => updateField('token_url', event.target.value)}
              />
            </>
          ) : (
            <>
              <Field
                label="Metadata URL (optional)"
                value={form.metadata_url}
                onChange={(event) => updateField('metadata_url', event.target.value)}
              />
              <Field
                label="Entity ID"
                value={form.entity_id}
                onChange={(event) => updateField('entity_id', event.target.value)}
              />
              <Field
                label="SSO URL"
                value={form.sso_url}
                onChange={(event) => updateField('sso_url', event.target.value)}
              />
            </>
          )}
          {redirectUri ? (
            <div>
              <Text as="div" variant="micro" tone="tertiary">
                {protocol === 'saml' ? 'Assertion Consumer Service / callback' : 'Redirect URI'}
              </Text>
              <Mono as="div" style={{ marginTop: 4, wordBreak: 'break-all' }}>
                {selected?.acs_url || redirectUri}
              </Mono>
            </div>
          ) : null}
          <div className="raptor-users-pane-foot" style={{ display: 'flex', gap: 8 }}>
            <Button variant="contained" onClick={handleSave} disabled={loading} style={{ flex: 1 }}>
              {creating ? 'Create' : 'Save'}
            </Button>
            {!creating ? (
              <>
                <Button variant="outlined" onClick={handleTest} disabled={loading}>
                  Test
                </Button>
                <Button variant="outlined" onClick={handleDelete} disabled={loading}>
                  Delete
                </Button>
              </>
            ) : null}
          </div>
        </Surface>
      </div>

      <Surface style={{ marginTop: SPACE.x24, padding: SPACE.x16, display: 'flex', flexDirection: 'column', gap: SPACE.x16 }}>
        <Text variant="bodyStrong">Allowlist before first sign-in</Text>
        <Text variant="meta" tone="secondary">
          Add a username and email so the user can sign in with SSO before they exist in Keycloak. First
          successful SSO links the account. The whole IdP tenant is not admitted automatically.
        </Text>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: SPACE.x12 }}>
          <Field
            label="Username"
            value={allowUsername}
            onChange={(event) => setAllowUsername(event.target.value)}
            placeholder="jsmith"
          />
          <Field
            label="Email"
            value={allowEmail}
            onChange={(event) => setAllowEmail(event.target.value)}
            placeholder="jsmith@example.com"
          />
          <Combo
            label="Role"
            options={ROLE_OPTIONS}
            value={allowRole}
            onChange={(value) => setAllowRole(value || 'user')}
            disableClearable
          />
          <Combo
            label="Protocol"
            options={PROTOCOL_OPTIONS}
            value={allowProtocol}
            onChange={(value) => setAllowProtocol(value || 'oidc')}
            disableClearable
          />
        </div>
        <Button variant="contained" onClick={handleAllowlist} disabled={loading || !allowUsername || !allowEmail}>
          Allowlist for SSO
        </Button>
      </Surface>
    </div>
  );
};

export default SsoConnectionsPanel;
