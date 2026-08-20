import React from 'react';
import { Button, Field, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH } from '../constants';

const SecuritySection = ({
  loading,
  currentPassword,
  setCurrentPassword,
  newPassword,
  setNewPassword,
  retypePassword,
  setRetypePassword,
  onChangePassword
}) => (
  <div style={{ maxWidth: 480, display: 'flex', flexDirection: 'column', gap: SPACE.x16 }}>
    <Field
      label="Current password"
      type="password"
      value={currentPassword}
      onChange={(event) => setCurrentPassword(event.target.value)}
    />
    <Field
      label="New password"
      type="password"
      value={newPassword}
      onChange={(event) => setNewPassword(event.target.value)}
    />
    <Field
      label="Confirm new password"
      type="password"
      value={retypePassword}
      onChange={(event) => setRetypePassword(event.target.value)}
    />
    <div>
      <Text as="div" variant="micro" tone="tertiary">
        NIST password requirements
      </Text>
      <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 4 }}>
        At least {MIN_PASSWORD_LENGTH} characters (max {MAX_PASSWORD_LENGTH}). Not a common password.
      </Text>
    </div>
    <Button variant="contained" onClick={onChangePassword} disabled={loading}>
      Update password
    </Button>
  </div>
);

export default SecuritySection;
