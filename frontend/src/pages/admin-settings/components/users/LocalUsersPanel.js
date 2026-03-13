import React from 'react';
import {
  Alert,
  Button,
  Checkbox,
  FormControl,
  FormControlLabel,
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
      <FormControlLabel
        control={
          <Checkbox
            checked={localIsServiceAccount}
            onChange={(event) => setLocalIsServiceAccount(event.target.checked)}
          />
        }
        label="Create as service account (API-only, no password login)"
      />
      {!localIsServiceAccount && (
        <>
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
        </>
      )}
      <Button
        variant="contained"
        startIcon={<PersonAddIcon />}
        onClick={onCreateLocalUser}
        disabled={loading}
      >
        {localIsServiceAccount ? 'Create Service Account' : 'Create Local User'}
      </Button>
      <Typography variant="caption" color="text.secondary">
        {localIsServiceAccount
          ? 'Service accounts cannot sign in through UI and are intended for API key access only.'
          : 'Local users will be prompted to reset their password on first login.'}
      </Typography>
    </Stack>

    {!localIsServiceAccount && localTempPassword && (
      <Alert severity="info" sx={{ mt: 3 }}>
        Temporary password: <strong>{localTempPassword}</strong>
      </Alert>
    )}
  </>
);

export default LocalUsersPanel;
