import React from 'react';
import {
  Button,
  DataList,
  DataRow,
  EmptyState,
  Field,
  Mono,
  Panel,
  Surface,
  SwitchRow,
  Tag,
  Text
} from '../../../../design/primitives';
import { SPACE } from '../../../../design/tokens';
import SectionHeader from '../SectionHeader';

const SCOPE_OPTIONS = [
  { key: 'records.read', label: 'View Assets Dataset' },
  { key: 'pentests.read', label: 'View Pentests Dataset' }
];

const ServiceAccountsPanel = ({
  loading,
  serviceAccounts,
  selectedServiceAccountUsername,
  onSelectServiceAccount,
  createUsername,
  setCreateUsername,
  createScopes,
  onToggleCreateScope,
  createEndDate,
  setCreateEndDate,
  onCreateServiceAccountWithKey,
  selectedScopes,
  onToggleSelectedScope,
  selectedEndDate,
  setSelectedEndDate,
  onCreateKeyForSelectedServiceAccount,
  onSaveSelectedScopes,
  onRotateSelectedKey,
  visibleApiKey,
  onCopyVisibleApiKey,
  onDismissVisibleApiKey
}) => {
  const selectedAccount =
    serviceAccounts.find((account) => account.username === selectedServiceAccountUsername) || null;

  return (
    <div>
      <SectionHeader title="Service Accounts and API Keys" />
      <div className="raptor-users-split">
        <Surface
          className="raptor-users-pane"
          style={{ padding: SPACE.x16, gap: SPACE.x16 }}
        >
          <Text variant="bodyStrong">Create</Text>
          <Field
            label="Username"
            value={createUsername}
            onChange={(event) => setCreateUsername(event.target.value)}
            placeholder="svc.integrations"
          />
          <div>
            <Text as="div" variant="micro" tone="tertiary">
              Privileges
            </Text>
            {SCOPE_OPTIONS.map((scope) => (
              <SwitchRow
                key={scope.key}
                label={scope.label}
                checked={createScopes.includes(scope.key)}
                onChange={() => onToggleCreateScope(scope.key)}
              />
            ))}
          </div>
          <Field
            type="date"
            label="Key end date"
            value={createEndDate}
            onChange={(event) => setCreateEndDate(event.target.value)}
            hint="Blank = 90 days."
          />
          <div className="raptor-users-pane-foot">
            <Button
              variant="contained"
              onClick={onCreateServiceAccountWithKey}
              disabled={loading}
              style={{ width: '100%' }}
            >
              Create service account
            </Button>
          </div>
        </Surface>

        <Surface className="raptor-users-pane" style={{ padding: SPACE.x16 }}>
          <Text as="div" variant="bodyStrong" style={{ marginBottom: SPACE.x12 }}>
            Existing
          </Text>
          {serviceAccounts.length === 0 ? (
            <div className="raptor-users-pane-fill" style={{ justifyContent: 'center' }}>
              <EmptyState title="No service accounts yet" hint="Create one on the left." />
            </div>
          ) : (
            <DataList>
              {serviceAccounts.map((account) => (
                <DataRow
                  key={account.username}
                  id={account.username}
                  selected={selectedServiceAccountUsername === account.username}
                  onToggle={() => onSelectServiceAccount(account.username)}
                  title={<Text variant="bodyStrong">{account.username}</Text>}
                  meta={
                    <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 2 }}>
                      {account.has_api_key
                        ? `Expires ${account.expires_at || 'not set'}`
                        : 'No API key'}
                    </Text>
                  }
                  trailing={<Tag>{account.has_api_key ? 'Key active' : 'No key'}</Tag>}
                />
              ))}
            </DataList>
          )}

          {selectedAccount ? (
            <div style={{ marginTop: SPACE.x24 }}>
              <Text as="h2" variant="h2">
                {selectedAccount.username}
              </Text>
              <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 4 }}>
                Created {selectedAccount.added_date || 'unknown'}
              </Text>

              <div style={{ marginTop: SPACE.x12 }}>
                <Text as="div" variant="micro" tone="tertiary">
                  Privileges
                </Text>
                {SCOPE_OPTIONS.map((scope) => (
                  <SwitchRow
                    key={scope.key}
                    label={scope.label}
                    checked={selectedScopes.includes(scope.key)}
                    onChange={() => onToggleSelectedScope(scope.key)}
                    disabled={!selectedAccount.has_api_key}
                  />
                ))}
                <Button
                  variant="outlined"
                  onClick={onSaveSelectedScopes}
                  disabled={loading || !selectedAccount.has_api_key}
                >
                  Save privileges
                </Button>
              </div>

              <div style={{ marginTop: SPACE.x16 }}>
                {!selectedAccount.has_api_key ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x12 }}>
                    <Field
                      type="date"
                      label="Key end date"
                      value={selectedEndDate}
                      onChange={(event) => setSelectedEndDate(event.target.value)}
                      hint="Blank = 90 days."
                    />
                    <Button
                      variant="contained"
                      onClick={onCreateKeyForSelectedServiceAccount}
                      disabled={loading}
                    >
                      Create API key
                    </Button>
                  </div>
                ) : (
                  <div>
                    <Text as="div" variant="meta" tone="secondary">
                      Key {selectedAccount.key_created_at || 'unknown'} · Expires{' '}
                      {selectedAccount.expires_at || 'unknown'}
                    </Text>
                    <div style={{ display: 'flex', gap: SPACE.x8, marginTop: SPACE.x12 }}>
                      <Button variant="contained" onClick={onRotateSelectedKey} disabled={loading}>
                        Rotate key
                      </Button>
                    </div>
                    <Text as="div" variant="meta" tone="secondary" style={{ marginTop: SPACE.x8 }}>
                      RAPTOR shows the full key only once, right after you create or rotate it.
                    </Text>
                  </div>
                )}
              </div>
            </div>
          ) : null}
        </Surface>
      </div>

      <Panel
        open={Boolean(visibleApiKey)}
        onClose={onDismissVisibleApiKey}
        title="Copy this API key"
        actions={
          <>
            <Button variant="outlined" onClick={onCopyVisibleApiKey}>
              Copy
            </Button>
            <Button variant="contained" onClick={onDismissVisibleApiKey}>
              Done
            </Button>
          </>
        }
      >
        <Text variant="body">
          This is the only time the full key is shown. Copy it now — RAPTOR cannot display it again.
        </Text>
        <Mono style={{ display: 'block', marginTop: SPACE.x12, wordBreak: 'break-all' }}>
          {visibleApiKey}
        </Mono>
      </Panel>
    </div>
  );
};

export default ServiceAccountsPanel;
