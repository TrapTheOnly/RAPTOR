import React from 'react';
import {
  Avatar,
  Box,
  Chip,
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
import { Delete as DeleteIcon, People as PeopleIcon } from '@mui/icons-material';
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
  onTogglePermission,
  onDeleteUser
}) => {
  const theme = useTheme();

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
                      {user.username?.charAt(0)?.toUpperCase()}
                    </Avatar>
                    <Box flex={1}>
                      <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                        {user.username}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {user.email || 'No email'}
                      </Typography>
                    </Box>
                  </Box>

                  <Box display="flex" alignItems="center" justifyContent="space-between" gap={1}>
                    <FormControl size="small" sx={{ minWidth: 120 }}>
                      <Select
                        value={roleKey}
                        onChange={(event) => onRoleChange(user.username, event.target.value)}
                        size="small"
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

                  <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                    {getRoleMeta(roleKey).description}
                  </Typography>

                  <Box sx={{ mt: 1.5 }}>
                    <OptionalPermissionControls
                      roleKey={roleKey}
                      permissions={permissions}
                      onToggle={(permission) => onTogglePermission(user, permission)}
                    />
                  </Box>

                  <Box mt={1}>
                    <AuthTypeChip authType={user.auth_type} />
                  </Box>
                </Paper>
              </Grid>
            );
          })}
        </Grid>
      )}
    </>
  );
};

export default ExistingUsersPanel;
