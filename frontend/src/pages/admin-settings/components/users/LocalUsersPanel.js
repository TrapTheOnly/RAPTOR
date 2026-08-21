import React from 'react';
import { Button, Combo, Field, Surface, SwitchRow, Text } from '../../../../design/primitives';
import { SPACE } from '../../../../design/tokens';
import { ROLE_OPTIONS } from '../../constants';
import { normalizeOptionalPermissions } from '../../utils';
import OptionalPermissionControls from '../OptionalPermissionControls';
import SectionHeader from '../SectionHeader';

const LocalUsersPanel = ({
  loading,
  localUsername,
  setLocalUsername,
  localFullName,
  setLocalFullName,
  localIsServiceAccount,
  setLocalIsServiceAccount,
  localRole,
  localPermissions,
  localTempPassword,
  onRoleChange,
  onTogglePermission,
  onCreateLocalUser
}) => (
  <>
    <SectionHeader title="Add Local Users" />
    <div className="raptor-users-split">
      <Surface
        className="raptor-users-pane"
        style={{ padding: SPACE.x16, gap: SPACE.x16 }}
      >
        <Text variant="bodyStrong">Identity</Text>
        <Field
          label="Username"
          value={localUsername}
          onChange={(event) => setLocalUsername(event.target.value)}
          placeholder="local.user"
        />
        <SwitchRow
          label="Service account"
          checked={localIsServiceAccount}
          onChange={setLocalIsServiceAccount}
        />
        {!localIsServiceAccount ? (
          <Field
            label="Full name"
            value={localFullName}
            onChange={(event) => setLocalFullName(event.target.value)}
            placeholder="Optional"
          />
        ) : null}
        <div className="raptor-users-pane-foot">
          <Button variant="contained" onClick={onCreateLocalUser} disabled={loading} style={{ width: '100%' }}>
            {localIsServiceAccount ? 'Create service account' : 'Create local user'}
          </Button>
          {!localIsServiceAccount && localTempPassword ? (
            <div style={{ marginTop: SPACE.x12 }}>
              <Text as="div" variant="micro" tone="tertiary">
                Temporary password
              </Text>
              <Text as="div" variant="bodyStrong" style={{ marginTop: 4 }}>
                {localTempPassword}
              </Text>
            </div>
          ) : null}
        </div>
      </Surface>

      <Surface
        className="raptor-users-pane"
        style={{ padding: SPACE.x16, gap: SPACE.x16 }}
      >
        {localIsServiceAccount ? (
          <Text variant="meta" tone="secondary">
            API-only. Set privileges and issue a key on the Service accounts tab after create.
          </Text>
        ) : (
          <>
            <Text variant="bodyStrong">Access</Text>
            <Combo
              label="Role"
              options={ROLE_OPTIONS}
              value={localRole}
              onChange={(next) => next && onRoleChange(next)}
              disableClearable
            />
            <OptionalPermissionControls
              roleKey={localRole}
              permissions={normalizeOptionalPermissions(localRole, localPermissions)}
              onToggle={onTogglePermission}
              compact
            />
            <div className="raptor-users-pane-foot">
              <Text variant="meta" tone="secondary">
                Password reset is required on first login.
              </Text>
            </div>
          </>
        )}
      </Surface>
    </div>
  </>
);

export default LocalUsersPanel;
