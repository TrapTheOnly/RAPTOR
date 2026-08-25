import React from 'react';
import { SwitchRow, Text } from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { OPTIONAL_PERMISSION_LABELS } from '../constants';
import { getOptionalPermissions } from '../utils';

const OptionalPermissionControls = ({ roleKey, permissions, onToggle, compact = false }) => {
  const optionalPermissions = getOptionalPermissions(roleKey);

  return (
    <div style={{ marginTop: compact ? SPACE.x8 : SPACE.x12 }}>
      <Text as="div" variant="micro" tone="tertiary">
        Optional permissions
      </Text>
      {optionalPermissions.length === 0 ? (
        <Text as="p" variant="meta" tone="secondary" style={{ margin: `${SPACE.x8}px 0 0` }}>
          None for this role.
        </Text>
      ) : (
        <div>
          {optionalPermissions.map((permission) => {
            const meta = OPTIONAL_PERMISSION_LABELS[permission] || {
              label: permission,
              description: ''
            };
            return (
              <SwitchRow
                key={permission}
                label={meta.label}
                hint={compact ? undefined : meta.description}
                checked={permissions.includes(permission)}
                onChange={() => onToggle(permission)}
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export default OptionalPermissionControls;
