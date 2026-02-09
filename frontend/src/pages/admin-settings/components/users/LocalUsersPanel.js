import React from 'react';
import {
  Alert,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import { AdminPanelSettings as AdminIcon, PersonAdd as PersonAddIcon } from '@mui/icons-material';
import { ROLE_OPTIONS } from '../../constants';
import { getRoleMeta, normalizeOptionalPermissions } from '../../utils';
import OptionalPermissionControls from '../OptionalPermissionControls';
import SectionHeader from '../SectionHeader';

const LocalUsersPanel = ({
  loading,
  localUsername,
  setLocalUsername,
  localRole,
  localPermissions,
  localTempPassword,
  onRoleChange,
  onTogglePermission,
  onCreateLocalUser
}) => (
  <>
    <SectionHeader icon={AdminIcon} title="Add Local Users" />

    <Stack spacing={2}>
      <TextField
        label="Username"
        variant="outlined"
        fullWidth
        value={localUsername}
        onChange={(event) => setLocalUsername(event.target.value)}
        placeholder="local.user"
      />
      <FormControl fullWidth size="small">
        <InputLabel id="local-user-role-label">Role</InputLabel>
        <Select
          labelId="local-user-role-label"
          value={localRole}
          label="Role"
          onChange={(event) => onRoleChange(event.target.value)}
          sx={{
            backgroundColor: 'background.paper',
            transition: 'all 0.2s ease'
          }}
        >
          {ROLE_OPTIONS.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
        {getRoleMeta(localRole).description}
      </Typography>
      <OptionalPermissionControls
        roleKey={localRole}
        permissions={normalizeOptionalPermissions(localRole, localPermissions)}
        onToggle={onTogglePermission}
      />
      <Button
        variant="contained"
        startIcon={<PersonAddIcon />}
        onClick={onCreateLocalUser}
        disabled={loading}
      >
        Create Local User
      </Button>
      <Typography variant="caption" color="text.secondary">
        Local users will be prompted to reset their password on first login.
      </Typography>
    </Stack>

    {localTempPassword && (
      <Alert severity="info" sx={{ mt: 3 }}>
        Temporary password: <strong>{localTempPassword}</strong>
      </Alert>
    )}
  </>
);

export default LocalUsersPanel;
