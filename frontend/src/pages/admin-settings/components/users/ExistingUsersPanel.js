import React, { useMemo, useState } from 'react';
import {
  Avatar,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  Grid,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Tooltip,
  Typography
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  Delete as DeleteIcon,
  Edit as EditIcon,
  ManageAccounts as ManageAccountsIcon,
  People as PeopleIcon
} from '@mui/icons-material';
import { ROLE_OPTIONS } from '../../constants';
import { getRoleMeta, normalizeOptionalPermissions } from '../../utils';
import AuthTypeChip from '../AuthTypeChip';
import OptionalPermissionControls from '../OptionalPermissionControls';
import SectionHeader from '../SectionHeader';

const ExistingUsersPanel = ({
  existingUsers,
  editedUserRoles,
  editedUserPermissions,
  onRoleChange,
  onSavePermissions,
  onDeleteUser
}) => {
  const theme = useTheme();
  const [editingUser, setEditingUser] = useState(null);
  const [dialogRole, setDialogRole] = useState('user');
  const [dialogPermissions, setDialogPermissions] = useState([]);

  const selectedUser = useMemo(
    () => existingUsers.find((user) => user.username === editingUser) || null,
    [editingUser, existingUsers]
  );

  const getRolePalette = (roleKey) => {
    const colorByRole = {
      admin: '#F44336',
      pentester: '#FF9800',
      user: '#4CAF50',
      manager: '#00897B'
    };
    return colorByRole[roleKey] || theme.palette.text.secondary;
  };

  const openAccessDialog = (user) => {
    if (user.is_service_account) return;
    const roleKey = editedUserRoles[user.username] || user.role;
    const permissions = normalizeOptionalPermissions(
      roleKey,
      editedUserPermissions[user.username] ?? user.permissions ?? []
    );

    setEditingUser(user.username);
    setDialogRole(roleKey);
    setDialogPermissions(permissions);
  };

  const closeAccessDialog = () => {
    setEditingUser(null);
    setDialogRole('user');
    setDialogPermissions([]);
  };

  const handleDialogRoleChange = (nextRole) => {
    setDialogRole(nextRole);
    setDialogPermissions((prev) => normalizeOptionalPermissions(nextRole, prev));
  };

  const handleDialogPermissionToggle = (permission) => {
    const current = normalizeOptionalPermissions(dialogRole, dialogPermissions);
    const next = current.includes(permission)
      ? current.filter((perm) => perm !== permission)
      : [...current, permission];
    setDialogPermissions(next);
  };

  const saveAccessChanges = async () => {
    if (!selectedUser) return;

    const nextRole = dialogRole;
    const nextPermissions = normalizeOptionalPermissions(dialogRole, dialogPermissions);
    const previousRole = editedUserRoles[selectedUser.username] || selectedUser.role;

    if (nextRole !== previousRole) {
      await onRoleChange(selectedUser.username, nextRole);
    }
    await onSavePermissions(selectedUser.username, nextRole, nextPermissions);
    closeAccessDialog();
  };

  return (
    <>
      <SectionHeader icon={PeopleIcon} title="Existing Users">
        <Chip
          label={`${existingUsers.length} users`}
          size="small"
          sx={{
            ml: 2,
            backgroundColor: alpha(theme.palette.info.main, 0.1),
            color: theme.palette.info.main
          }}
        />
      </SectionHeader>

      {existingUsers.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <PeopleIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No users found
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Add users to get started
          </Typography>
        </Box>
      ) : (
        <Grid container spacing={2}>
          {existingUsers.map((user) => {
            const roleKey = editedUserRoles[user.username] || user.role;
            const permissions = normalizeOptionalPermissions(
              roleKey,
              editedUserPermissions[user.username] ?? user.permissions ?? []
            );

            return (
              <Grid item xs={12} sm={6} md={4} key={user.username}>
                <Paper
                  sx={{
                    p: 2,
                    height: '100%',
                    backgroundColor: 'background.default',
                    border: `1px solid ${theme.palette.divider}`,
                    '&:hover': {
                      borderColor: theme.palette.primary.main,
                      backgroundColor: alpha(theme.palette.primary.main, 0.02)
                    },
                    transition: 'all 0.2s ease-in-out'
                  }}
                >
                  <Box display="flex" alignItems="center" mb={2}>
                    <Avatar sx={{ mr: 1 }}>
                      {(user.full_name || user.username)?.charAt(0)?.toUpperCase()}
                    </Avatar>
                    <Box flex={1} minWidth={0}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 600 }} noWrap>
                        {user.full_name || user.username}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" noWrap>
                        {user.full_name ? user.username : (user.email || 'No email')}
                      </Typography>
                    </Box>
                  </Box>

                  <Box display="flex" alignItems="center" justifyContent="space-between" gap={1}>
                    {user.is_service_account ? (
                      <Chip
                        label="Service Account"
                        size="small"
                        sx={{
                          fontWeight: 600,
                          backgroundColor: alpha(theme.palette.success.main, 0.14),
                          color: theme.palette.success.main,
                          border: `1px solid ${alpha(theme.palette.success.main, 0.35)}`
                        }}
                      />
                    ) : (
                      <Chip
                        label={getRoleMeta(roleKey).label}
                        size="small"
                        sx={{
                          fontWeight: 600,
                          backgroundColor: alpha(getRolePalette(roleKey), 0.14),
                          color: getRolePalette(roleKey),
                          border: `1px solid ${alpha(getRolePalette(roleKey), 0.35)}`
                        }}
                      />
                    )}
                    <Box display="flex" alignItems="center" gap={0.5}>
                      <Tooltip title="Edit role and permissions">
                        <span>
                          <IconButton
                            color="primary"
                            onClick={() => openAccessDialog(user)}
                            size="small"
                            disabled={Boolean(user.is_service_account)}
                          >
                            <EditIcon />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Delete User">
                        <IconButton
                          color="error"
                          onClick={() => onDeleteUser(user.username)}
                          size="small"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Tooltip>
                    </Box>
                  </Box>

                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    {user.is_service_account
                      ? 'API-only identity. Manage scopes and keys in Service Accounts section.'
                      : getRoleMeta(roleKey).description}
                  </Typography>

                  <Box display="flex" alignItems="center" gap={1} mt={1}>
                    <Chip
                      size="small"
                      variant="outlined"
                      label={`${permissions.length} optional permission${permissions.length === 1 ? '' : 's'}`}
                    />
                    <AuthTypeChip authType={user.auth_type} />
                  </Box>
                </Paper>
              </Grid>
            );
          })}
        </Grid>
      )}

      <Dialog
        open={Boolean(selectedUser)}
        onClose={closeAccessDialog}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 2.5,
            border: `1px solid ${theme.palette.divider}`,
            backgroundColor: theme.palette.background.paper
          }
        }}
      >
        <DialogTitle sx={{ borderBottom: `1px solid ${theme.palette.divider}` }}>
          <Box display="flex" alignItems="center" gap={1.25}>
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: 1.5,
                backgroundColor: alpha(theme.palette.primary.main, 0.12),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <ManageAccountsIcon sx={{ color: theme.palette.primary.main, fontSize: 20 }} />
            </Box>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                {selectedUser ? `Edit Access: ${selectedUser.full_name || selectedUser.username}` : 'Edit Access'}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                Update role and optional permissions
              </Typography>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2 }}>
            <Paper
              variant="outlined"
              sx={{
                p: 1.5,
                backgroundColor: alpha(theme.palette.background.default, 0.7),
                borderColor: alpha(theme.palette.divider, 0.7)
              }}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mb: 0.75, fontWeight: 700, letterSpacing: 0.5, textTransform: 'uppercase' }}
              >
                Role
              </Typography>
              <FormControl size="small" fullWidth>
                <Select
                  value={dialogRole}
                  onChange={(event) => handleDialogRoleChange(event.target.value)}
                  sx={{ backgroundColor: theme.palette.background.paper }}
                >
                  {ROLE_OPTIONS.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              <Box display="flex" alignItems="center" gap={1} mt={1}>
                <Chip
                  size="small"
                  label={getRoleMeta(dialogRole).label}
                  sx={{
                    fontWeight: 600,
                    backgroundColor: alpha(getRolePalette(dialogRole), 0.14),
                    color: getRolePalette(dialogRole),
                    border: `1px solid ${alpha(getRolePalette(dialogRole), 0.35)}`
                  }}
                />
                <Typography variant="caption" color="text.secondary">
                  {getRoleMeta(dialogRole).description}
                </Typography>
              </Box>
            </Paper>

            <OptionalPermissionControls
              roleKey={dialogRole}
              permissions={normalizeOptionalPermissions(dialogRole, dialogPermissions)}
              onToggle={handleDialogPermissionToggle}
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={closeAccessDialog} variant="outlined">
            Cancel
          </Button>
          <Button variant="contained" onClick={saveAccessChanges}>
            Save
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default ExistingUsersPanel;
