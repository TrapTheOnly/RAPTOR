import React from 'react';
import { Button, Combo, Field, Surface, Text } from '../../../../design/primitives';
import { SPACE } from '../../../../design/tokens';
import { ROLE_OPTIONS } from '../../constants';
import { normalizeOptionalPermissions } from '../../utils';
import OptionalPermissionControls from '../OptionalPermissionControls';
import SectionHeader from '../SectionHeader';

const DomainUsersPanel = ({
  loading,
  searchQuery,
  setSearchQuery,
  searchResults,
  existingUsers,
  selectedUsers,
  selectedUserRoles,
  selectedUserPermissions,
  onSearch,
  onSelectUser,
  onRemoveUser,
  onSelectedRoleChange,
  onSelectedPermissionToggle,
  onSubmit
}) => {
  const available = searchResults.filter(
    (user) => !existingUsers.some((existingUser) => existingUser.username === user.username)
  );

  return (
    <>
      <SectionHeader title="Add LDAP Users" />
      <div className="raptor-users-split">
        <Surface
          className="raptor-users-pane"
          style={{
            padding: SPACE.x16,
            minHeight: 420,
            gap: SPACE.x12
          }}
        >
          <Text variant="bodyStrong">Directory</Text>
          <div style={{ display: 'flex', gap: SPACE.x8, alignItems: 'flex-end' }}>
            <Field
              label="Search"
              placeholder="Name or username"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyDown={(event) => event.key === 'Enter' && onSearch()}
            />
            <Button variant="contained" size="small" onClick={onSearch} disabled={loading}>
              Search
            </Button>
          </div>
          <div style={{ flex: 1, overflow: 'auto', minHeight: 280 }}>
            {available.length === 0 ? (
              <Text variant="meta" tone="secondary">
                Search the directory, then add people from the results.
              </Text>
            ) : (
              available.map((user) => (
                <button
                  key={user.username}
                  type="button"
                  onClick={() => onSelectUser(user)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    border: 0,
                    background: 'transparent',
                    padding: `${SPACE.x8}px 0`,
                    cursor: 'pointer',
                    borderBottom: '1px solid var(--raptor-line)'
                  }}
                >
                  <Text as="div" variant="bodyStrong">
                    {user.full_name || user.username}
                  </Text>
                  <Text as="div" variant="meta" tone="secondary">
                    {user.username}
                    {user.email ? ` · ${user.email}` : ''}
                    {user.source ? ` · ${user.source}` : ''}
                  </Text>
                </button>
              ))
            )}
          </div>
        </Surface>

        <Surface
          className="raptor-users-pane"
          style={{
            padding: SPACE.x16,
            minHeight: 420,
            gap: SPACE.x12
          }}
        >
          <Text variant="bodyStrong">{`Selected (${selectedUsers.length})`}</Text>
          <div style={{ flex: 1, overflow: 'auto', minHeight: 280 }}>
            {selectedUsers.length === 0 ? (
              <Text variant="meta" tone="secondary">
                Click a directory result to queue it here.
              </Text>
            ) : (
              selectedUsers.map((user) => {
                const roleKey = selectedUserRoles[user.username] || 'user';
                const permissions = normalizeOptionalPermissions(
                  roleKey,
                  selectedUserPermissions[user.username] || []
                );
                return (
                  <div
                    key={user.username}
                    style={{
                      padding: `${SPACE.x12}px 0`,
                      borderBottom: '1px solid var(--raptor-line)'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: SPACE.x8 }}>
                      <div style={{ minWidth: 0 }}>
                        <Text as="div" variant="bodyStrong">
                          {user.full_name || user.username}
                        </Text>
                        <Text as="div" variant="meta" tone="secondary">
                          {user.username}
                        </Text>
                      </div>
                      <Button size="small" variant="outlined" onClick={() => onRemoveUser(user)}>
                        Remove
                      </Button>
                    </div>
                    <div style={{ marginTop: SPACE.x8 }}>
                      <Combo
                        label="Role"
                        options={ROLE_OPTIONS}
                        value={roleKey}
                        onChange={(next) => next && onSelectedRoleChange(user.username, next)}
                        disableClearable
                      />
                      <OptionalPermissionControls
                        roleKey={roleKey}
                        permissions={permissions}
                        onToggle={(permission) => onSelectedPermissionToggle(user.username, permission)}
                        compact
                      />
                    </div>
                  </div>
                );
              })
            )}
          </div>
          {selectedUsers.length > 0 ? (
            <Button variant="contained" onClick={onSubmit} disabled={loading}>
              Add selected users
            </Button>
          ) : null}
        </Surface>
      </div>
    </>
  );
};

export default DomainUsersPanel;
