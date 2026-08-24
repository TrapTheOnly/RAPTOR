import axios from 'axios';
import { AnimatePresence, motion, useReducedMotion } from 'motion/react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Button,
  Combo,
  EmptyState,
  Field,
  Mono,
  Rule,
  Segmented,
  Skeleton,
  Surface,
  SwitchRow,
  Text
} from '../../../../design/primitives';
import { EASE, SECONDS, TRANSITION } from '../../../../design/motion';
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

const stack = {
  display: 'flex',
  flexDirection: 'column',
  gap: SPACE.x16
};

const suggestAlias = (name) =>
  String(name || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);

const copyText = async (value, showMessage) => {
  try {
    await navigator.clipboard.writeText(value);
    showMessage?.('success', 'Copied to clipboard.');
  } catch (error) {
    showMessage?.('error', 'Could not copy to clipboard.');
  }
};

const CopyRow = ({ label, hint, value, showMessage }) => {
  if (!value) return null;
  return (
    <div>
      <Text as="div" variant="micro" tone="tertiary">
        {label}
      </Text>
      {hint ? (
        <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 2 }}>
          {hint}
        </Text>
      ) : null}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start', marginTop: 4 }}>
        <Mono as="div" style={{ flex: 1, wordBreak: 'break-all' }}>
          {value}
        </Mono>
        <Button variant="outlined" onClick={() => copyText(value, showMessage)}>
          Copy
        </Button>
      </div>
    </div>
  );
};

const HowItWorks = () => {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: SPACE.x16 }}>
      <Button variant="text" size="small" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
        {open ? 'Hide how it works' : 'How it works'}
      </Button>
      {open ? (
        <div style={{ ...stack, gap: SPACE.x8, marginTop: SPACE.x8, maxWidth: '65ch' }}>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
            RAPTOR uses Keycloak as the protocol engine. Never paste Flask /auth/sso/callback into the
            IdP.
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
            Okta/Entra tiles must use the Start URL, not an unsolicited ACS.
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
            Only allowlisted usernames get in. Username must match the IdP preferred_username.
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
            Alias and protocol lock after create.
          </Text>
        </div>
      ) : null}
    </div>
  );
};

const ConnectionFields = ({
  form,
  protocol,
  creating,
  showAdvanced,
  onField,
  onProtocol,
  onDisplayName,
  onToggleAdvanced
}) => (
  <>
    {creating ? (
      <div>
        <Text as="div" variant="micro" tone="tertiary" style={{ marginBottom: 6 }}>
          Protocol
        </Text>
        <Segmented value={protocol} onChange={(value) => onProtocol(value || 'oidc')} options={PROTOCOL_OPTIONS} />
      </div>
    ) : null}
    <Field
      label="Display name"
      value={form.display_name}
      onChange={(event) => onDisplayName(event.target.value)}
      placeholder="Corporate SSO"
      hint="Shown on the RAPTOR login button"
    />
    <Field
      label="Alias"
      value={form.alias}
      onChange={(event) => onField('alias', event.target.value)}
      placeholder="corp-oidc"
      disabled={!creating}
      hint={
        creating
          ? 'Lowercase letters, numbers, and hyphens. Locked after create.'
          : 'Locked after create.'
      }
    />
    {protocol === 'oidc' ? (
      <>
        <Field
          label="Issuer"
          value={form.issuer}
          onChange={(event) => onField('issuer', event.target.value)}
          placeholder="https://idp.example.com/oauth2/default"
        />
        <Field
          label="Client ID"
          value={form.client_id}
          onChange={(event) => onField('client_id', event.target.value)}
        />
        <Field
          label="Client secret"
          type="password"
          value={form.client_secret}
          onChange={(event) => onField('client_secret', event.target.value)}
          placeholder={creating ? '' : 'Leave blank to keep'}
        />
      </>
    ) : (
      <Field
        label="IdP metadata URL"
        value={form.metadata_url}
        onChange={(event) => onField('metadata_url', event.target.value)}
        placeholder="https://idp.example.com/app/sso/saml/metadata"
        hint="Preferred. Paste Okta/Entra IdP metadata URL."
      />
    )}
    <div>
      <Button variant="outlined" onClick={onToggleAdvanced}>
        {showAdvanced ? 'Hide advanced endpoints' : 'Advanced endpoints'}
      </Button>
    </div>
    {showAdvanced && protocol === 'oidc' ? (
      <>
        <Field
          label="Authorization URL"
          value={form.authorization_url}
          onChange={(event) => onField('authorization_url', event.target.value)}
        />
        <Field
          label="Token URL"
          value={form.token_url}
          onChange={(event) => onField('token_url', event.target.value)}
        />
        <Field
          label="JWKS URL"
          value={form.jwks_url}
          onChange={(event) => onField('jwks_url', event.target.value)}
        />
        <Field
          label="Logout URL"
          value={form.logout_url}
          onChange={(event) => onField('logout_url', event.target.value)}
        />
      </>
    ) : null}
    {showAdvanced && protocol === 'saml' ? (
      <>
        <Field
          label="IdP Entity ID"
          value={form.entity_id}
          onChange={(event) => onField('entity_id', event.target.value)}
          hint="Identity provider entity ID from Okta/Entra metadata - not RAPTOR's SP Entity ID."
        />
        <Field
          label="IdP SSO URL"
          value={form.sso_url}
          onChange={(event) => onField('sso_url', event.target.value)}
        />
      </>
    ) : null}
  </>
);

const SsoConnectionsPanel = ({ showMessage }) => {
  const reduceMotion = useReducedMotion();
  const firstCopyRef = useRef(null);
  const deleteTriggerRef = useRef(null);
  const [connections, setConnections] = useState([]);
  const [selectedAlias, setSelectedAlias] = useState('');
  const [form, setForm] = useState(EMPTY_FORM);
  const [mode, setMode] = useState('empty');
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState('');
  const [aliasTouched, setAliasTouched] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [allowUsername, setAllowUsername] = useState('');
  const [allowEmail, setAllowEmail] = useState('');
  const [allowRole, setAllowRole] = useState('user');
  const [inviteLinks, setInviteLinks] = useState([]);
  const [lastAllowlisted, setLastAllowlisted] = useState('');
  const [justCreated, setJustCreated] = useState(false);

  const selected = useMemo(
    () => connections.find((row) => row.alias === selectedAlias) || null,
    [connections, selectedAlias]
  );

  const load = useCallback(async () => {
    const response = await axios.get('/sso/connections');
    const rows = response.data?.connections || [];
    setConnections(rows);
    return rows;
  }, []);

  const selectConnection = useCallback((row) => {
    setMode('workspace');
    setSelectedAlias(row.alias);
    setAliasTouched(true);
    setShowAdvanced(Boolean(row.entity_id || row.sso_url || row.authorization_url || row.token_url));
    setShowSettings(false);
    setShowDeleteConfirm(false);
    setInviteLinks([]);
    setLastAllowlisted('');
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
  }, []);

  useEffect(() => {
    load()
      .then((rows) => {
        if (rows.length) selectConnection(rows[0]);
        else setMode('empty');
      })
      .catch(() => {
        showMessage?.('error', 'Could not load SSO connections.');
        setMode('empty');
      })
      .finally(() => setHydrated(true));
  }, [load, selectConnection, showMessage]);

  useEffect(() => {
    if (!justCreated || !firstCopyRef.current) return;
    const copyButton = firstCopyRef.current.querySelector('button');
    copyButton?.focus();
    setJustCreated(false);
  }, [justCreated, selected]);

  useEffect(() => {
    if (!showDeleteConfirm) return undefined;
    const onKey = (event) => {
      if (event.key !== 'Escape') return;
      setShowDeleteConfirm(false);
      deleteTriggerRef.current?.querySelector('button')?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [showDeleteConfirm]);

  const updateField = (key, value) => {
    if (key === 'alias') setAliasTouched(true);
    setForm((current) => ({ ...current, [key]: value }));
  };

  const handleDisplayName = (value) => {
    setForm((current) => ({
      ...current,
      display_name: value,
      alias: mode === 'creating' && !aliasTouched ? suggestAlias(value) : current.alias
    }));
  };

  const startCreate = () => {
    setMode('creating');
    setForm(EMPTY_FORM);
    setAliasTouched(false);
    setShowAdvanced(false);
    setShowSettings(false);
    setShowDeleteConfirm(false);
    setInviteLinks([]);
    setLastAllowlisted('');
  };

  const cancelCreate = () => {
    const row = connections.find((item) => item.alias === selectedAlias) || connections[0];
    if (row) selectConnection(row);
    else {
      setMode('empty');
      setForm(EMPTY_FORM);
    }
  };

  const handleSave = async () => {
    setBusy('saving');
    try {
      if (mode === 'creating') {
        await axios.post('/sso/connections', form);
        const rows = await load();
        const created = rows.find((row) => row.alias === form.alias);
        if (created) {
          selectConnection(created);
          setJustCreated(true);
        }
      } else {
        const payload = { ...form };
        if (!payload.client_secret) delete payload.client_secret;
        await axios.put(`/sso/connections/${encodeURIComponent(selectedAlias)}`, payload);
        showMessage?.('success', 'SSO connection saved.');
        const rows = await load();
        const updated = rows.find((row) => row.alias === selectedAlias);
        if (updated) selectConnection(updated);
      }
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Could not save SSO connection.');
    } finally {
      setBusy('');
    }
  };

  const handleTest = async () => {
    if (!selectedAlias) return;
    setBusy('testing');
    try {
      const response = await axios.post(`/sso/connections/${encodeURIComponent(selectedAlias)}/test`);
      showMessage?.('success', response.data?.message || 'Connection test succeeded.');
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Connection test failed.');
    } finally {
      setBusy('');
    }
  };

  const handleDelete = async () => {
    if (!selectedAlias) return;
    setBusy('deleting');
    try {
      await axios.delete(`/sso/connections/${encodeURIComponent(selectedAlias)}`);
      showMessage?.('success', 'SSO connection deleted.');
      const rows = await load();
      if (rows.length) selectConnection(rows[0]);
      else {
        setSelectedAlias('');
        setForm(EMPTY_FORM);
        setMode('empty');
        setShowDeleteConfirm(false);
      }
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Could not delete SSO connection.');
    } finally {
      setBusy('');
    }
  };

  const handleDownloadMetadata = async () => {
    if (!selectedAlias) return;
    setBusy('downloading');
    try {
      const response = await axios.get(
        `/sso/connections/${encodeURIComponent(selectedAlias)}/sp-metadata`,
        { responseType: 'blob' }
      );
      const blob = new Blob([response.data], { type: 'application/samlmetadata+xml' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${selectedAlias}-sp-metadata.xml`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Could not download SP metadata.');
    } finally {
      setBusy('');
    }
  };

  const handleAllowlist = async () => {
    if (!selected) return;
    setBusy('allowlisting');
    try {
      const response = await axios.post('/sso/allowlist', {
        username: allowUsername,
        email: allowEmail,
        role: allowRole,
        auth_type: selected.protocol || 'oidc'
      });
      const urls = response.data?.start_urls || [];
      const scoped = urls.filter((row) => row.alias === selected.alias);
      setInviteLinks(scoped.length ? scoped : urls);
      setLastAllowlisted(allowUsername);
      showMessage?.(
        'success',
        response.data?.email_sent
          ? `Allowlisted ${allowUsername}. Copy the start URL below; an invite email was also sent.`
          : `Allowlisted ${allowUsername}. Copy the start URL below. This is not a password.`
      );
      setAllowUsername('');
      setAllowEmail('');
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || 'Could not allowlist user.');
    } finally {
      setBusy('');
    }
  };

  const protocol = form.protocol || 'oidc';
  const paneMotion = {
    initial: reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.96 },
    animate: { opacity: 1, scale: 1, transition: { duration: SECONDS.slow, ease: EASE.enter } },
    exit: reduceMotion ? { opacity: 0 } : { opacity: 0, y: 4, transition: TRANSITION.exit }
  };

  const headerActions =
    hydrated && mode === 'workspace' ? (
      <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8 }}>
        {connections.length > 1 ? (
          <Combo
            options={connections.map((row) => ({
              value: row.alias,
              label: row.display_name || row.alias
            }))}
            value={selectedAlias}
            onChange={(alias) => {
              const row = connections.find((item) => item.alias === alias);
              if (row) selectConnection(row);
            }}
            disableClearable
            fullWidth={false}
            style={{ minWidth: 180, width: 220 }}
          />
        ) : null}
        <Button variant="outlined" onClick={startCreate}>
          New
        </Button>
      </div>
    ) : null;

  const fieldHandlers = {
    form,
    protocol,
    showAdvanced,
    onField: updateField,
    onProtocol: (value) => updateField('protocol', value),
    onDisplayName: handleDisplayName,
    onToggleAdvanced: () => setShowAdvanced((open) => !open)
  };

  return (
    <div>
      <SectionHeader title="Sign-in / SSO">{headerActions}</SectionHeader>
      <Text as="p" variant="meta" tone="secondary" style={{ marginTop: 0, marginBottom: SPACE.x8 }}>
        Connect Okta or Entra so people can sign in to RAPTOR.
      </Text>
      <HowItWorks />

      {!hydrated ? <Skeleton height={160} /> : null}

      <AnimatePresence mode="wait" initial={false}>
        {hydrated && mode === 'empty' ? (
          <motion.div key="empty" {...paneMotion}>
            <EmptyState
              title="No company sign-in yet"
              hint="Create a connection, then paste RAPTOR's values into the IdP app."
              actions={
                <Button variant="contained" onClick={startCreate}>
                  Create connection
                </Button>
              }
            />
          </motion.div>
        ) : null}

        {hydrated && mode === 'creating' ? (
          <motion.div key="creating" {...paneMotion}>
            <Surface style={{ padding: SPACE.x16, ...stack }}>
              <Text variant="bodyStrong">Create connection</Text>
              <ConnectionFields creating {...fieldHandlers} />
              <div style={{ display: 'flex', gap: 8 }}>
                {connections.length > 0 ? (
                  <Button variant="outlined" onClick={cancelCreate} disabled={busy === 'saving'}>
                    Cancel
                  </Button>
                ) : null}
                <Button
                  variant="contained"
                  onClick={handleSave}
                  disabled={busy === 'saving'}
                  style={{ flex: 1 }}
                >
                  Create
                </Button>
              </div>
            </Surface>
          </motion.div>
        ) : null}

        {hydrated && mode === 'workspace' && selected ? (
          <motion.div key="workspace" {...paneMotion}>
            <Surface style={{ padding: SPACE.x16, ...stack }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8, flexWrap: 'wrap' }}>
                <Text variant="bodyStrong">{selected.display_name || selected.alias}</Text>
                <AuthTypeChip authType={selected.protocol} />
                {selected.enabled ? null : (
                  <Text variant="micro" tone="tertiary">
                    Disabled
                  </Text>
                )}
              </div>
              <Text as="p" variant="bodyStrong" style={{ margin: 0 }}>
                Paste these into the Okta / Entra app.
              </Text>
              <Text as="p" variant="meta" tone="secondary" style={{ margin: 0 }}>
                Tiles must use the Start URL. Do not use RAPTOR /auth/sso/callback.
              </Text>

              <div ref={firstCopyRef} style={{ ...stack, gap: SPACE.x12 }}>
                {selected.protocol === 'saml' ? (
                  <>
                    <CopyRow
                      label="Assertion Consumer Service / Reply URL / Single sign-on URL"
                      hint="Keycloak broker. Not /auth/sso/callback."
                      value={selected.acs_url}
                      showMessage={showMessage}
                    />
                    <CopyRow
                      label="Audience URI / Identifier (SP Entity ID)"
                      hint="RAPTOR/Keycloak SP entity ID - not the IdP Entity ID field in Okta."
                      value={selected.sp_entity_id}
                      showMessage={showMessage}
                    />
                    <CopyRow
                      label="Sign-on URL / Application start URL / Initiate login URI"
                      hint="Use this on the IdP app tile."
                      value={selected.start_url}
                      showMessage={showMessage}
                    />
                    <CopyRow
                      label="SP metadata URL"
                      value={selected.sp_metadata_url}
                      showMessage={showMessage}
                    />
                    {selected.sp_metadata_url ? (
                      <Button
                        variant="outlined"
                        onClick={handleDownloadMetadata}
                        disabled={busy === 'downloading'}
                      >
                        Download SP metadata XML
                      </Button>
                    ) : null}
                  </>
                ) : (
                  <>
                    <CopyRow
                      label="Sign-in redirect URI (corporate IdP)"
                      hint="Keycloak broker. Not /auth/sso/callback."
                      value={selected.broker_redirect_uri || selected.acs_url}
                      showMessage={showMessage}
                    />
                    <CopyRow
                      label="Initiate login URI / Sign-on URL"
                      hint="Use this on the IdP app tile."
                      value={selected.start_url}
                      showMessage={showMessage}
                    />
                  </>
                )}
              </div>

              <Rule />

              <Text variant="bodyStrong">Admit one person</Text>
              <Text variant="meta" tone="secondary">
                Username must match their IdP preferred_username.
              </Text>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: SPACE.x12
                }}
              >
                <Field
                  label="Username"
                  value={allowUsername}
                  onChange={(event) => setAllowUsername(event.target.value)}
                  placeholder="jsmith"
                  hint="Must match IdP preferred_username."
                />
                <Field
                  label="Email"
                  value={allowEmail}
                  onChange={(event) => setAllowEmail(event.target.value)}
                  placeholder="jsmith@example.com"
                  hint="Invite and display only."
                />
                <Combo
                  label="Role"
                  options={ROLE_OPTIONS}
                  value={allowRole}
                  onChange={(value) => setAllowRole(value || 'user')}
                  disableClearable
                />
              </div>
              <Button
                variant={showSettings ? 'outlined' : 'contained'}
                onClick={handleAllowlist}
                disabled={busy === 'allowlisting' || !allowUsername || !allowEmail}
              >
                Allowlist
              </Button>
              {inviteLinks.length > 0 ? (
                <div style={{ ...stack, gap: SPACE.x12 }}>
                  <Text variant="bodyStrong">
                    Start URL{lastAllowlisted ? ` for ${lastAllowlisted}` : ''}
                  </Text>
                  {inviteLinks.map((row) => (
                    <CopyRow
                      key={row.alias}
                      label={row.display_name || row.alias}
                      value={row.url}
                      showMessage={showMessage}
                    />
                  ))}
                </div>
              ) : null}

              <Button variant="outlined" onClick={handleTest} disabled={busy === 'testing'}>
                Test connection
              </Button>

              <Rule />

              <div>
                <Button variant="text" size="small" onClick={() => setShowSettings((open) => !open)}>
                  {showSettings ? 'Hide connection settings' : 'Connection settings'}
                </Button>
              </div>
              {showSettings ? (
                <div style={stack}>
                  <SwitchRow
                    label="Enabled"
                    checked={Boolean(form.enabled)}
                    onChange={(checked) => updateField('enabled', checked)}
                  />
                  <ConnectionFields creating={false} {...fieldHandlers} />
                  <Button variant="contained" onClick={handleSave} disabled={busy === 'saving'}>
                    Save
                  </Button>
                </div>
              ) : null}

              {showDeleteConfirm ? (
                <div style={stack}>
                  <Text variant="body">
                    Delete {selected.display_name || selected.alias}? People using this connection
                    will lose company sign-in.
                  </Text>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <Button
                      variant="outlined"
                      onClick={() => {
                        setShowDeleteConfirm(false);
                        deleteTriggerRef.current?.querySelector('button')?.focus();
                      }}
                    >
                      Cancel
                    </Button>
                    <Button
                      variant="contained"
                      color="error"
                      onClick={handleDelete}
                      disabled={busy === 'deleting'}
                    >
                      Delete connection
                    </Button>
                  </div>
                </div>
              ) : (
                <span ref={deleteTriggerRef}>
                  <Button variant="text" size="small" onClick={() => setShowDeleteConfirm(true)}>
                    Delete connection
                  </Button>
                </span>
              )}
            </Surface>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
};

export default SsoConnectionsPanel;
