import React from 'react';
import {
  Avatar,
  Box,
  Button,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  TextField,
  Typography
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  Delete as DeleteIcon,
  PersonAdd as PersonAddIcon,
  Search as SearchIcon
} from '@mui/icons-material';
import { ROLE_OPTIONS } from '../../constants';
import { getRoleMeta, normalizeOptionalPermissions } from '../../utils';
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
  const theme = useTheme();

  return (
    <>
      <SectionHeader icon={PersonAddIcon} title="Add LDAP Users" />

      <Box display="flex" gap={1} mb={2}>
        <TextField
          placeholder="Search domain user..."
          variant="outlined"
          size="small"
          fullWidth
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          onKeyDown={(event) => event.key === 'Enter' && onSearch()}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon />
              </InputAdornment>
            )
          }}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<SearchIcon />}
          onClick={onSearch}
          disabled={loading}
        >
          Search
        </Button>
      </Box>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 1, backgroundColor: 'background.default', height: 320, overflow: 'auto' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, px: 1 }}>
              Available Users
            </Typography>
            {searchResults.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                No users found
              </Typography>
            ) : (
              <List sx={{ p: 0 }}>
                {searchResults
                  .filter((user) => !existingUsers.some((existingUser) => existingUser.username === user.username))
                  .map((user) => (
                    <ListItem disablePadding key={user.username} sx={{ mb: 0.5 }}>
                      <ListItemButton
                        onClick={() => onSelectUser(user)}
                        sx={{
                          borderRadius: 1,
                          '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.05) }
                        }}
                      >
                        <Avatar sx={{ mr: 1, width: 24, height: 24, fontSize: '0.75rem' }}>
                          {user.full_name?.charAt(0) || user.username?.charAt(0)}
                        </Avatar>
                        <ListItemText
                          primary={user.full_name}
                          secondary={user.email}
                          primaryTypographyProps={{ fontSize: '0.875rem' }}
                          secondaryTypographyProps={{ fontSize: '0.75rem' }}
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
              </List>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 1, backgroundColor: 'background.default', height: 320, overflow: 'auto' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1, px: 1 }}>
              Selected Users ({selectedUsers.length})
            </Typography>
            {selectedUsers.length === 0 ? (
              <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                No users selected
              </Typography>
            ) : (
              <List sx={{ p: 0 }}>
                {selectedUsers.map((user) => {
                  const roleKey = selectedUserRoles[user.username] || 'user';
                  const permissions = normalizeOptionalPermissions(
                    roleKey,
                    selectedUserPermissions[user.username] || []
                  );

                  return (
                    <ListItem
                      key={user.username}
                      sx={{
                        border: `1px solid ${theme.palette.divider}`,
                        borderRadius: 1,
                        mb: 1,
                        backgroundColor: 'background.paper'
                      }}
                    >
                      <Avatar sx={{ mr: 1, width: 24, height: 24, fontSize: '0.75rem' }}>
                        {user.full_name?.charAt(0) || user.username?.charAt(0)}
                      </Avatar>
                      <ListItemText
                        primary={user.full_name}
                        secondary={
                          <Box sx={{ mt: 0.5 }}>
                            <FormControl size="small" sx={{ minWidth: 120 }}>
                              <Select
                                value={roleKey}
                                onChange={(event) => onSelectedRoleChange(user.username, event.target.value)}
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
                            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                              {getRoleMeta(roleKey).description}
                            </Typography>
                            <OptionalPermissionControls
                              roleKey={roleKey}
                              permissions={permissions}
                              onToggle={(permission) => onSelectedPermissionToggle(user.username, permission)}
                            />
                          </Box>
                        }
                        primaryTypographyProps={{ fontSize: '0.875rem' }}
                      />
                      <IconButton
                        edge="end"
                        color="error"
                        onClick={() => onRemoveUser(user)}
                        size="small"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </ListItem>
                  );
                })}
              </List>
            )}
            {selectedUsers.length > 0 && (
              <Button
                variant="contained"
                color="secondary"
                startIcon={<PersonAddIcon />}
                onClick={onSubmit}
                disabled={loading}
                fullWidth
                sx={{ mt: 1 }}
              >
                Add Selected Users
              </Button>
            )}
          </Paper>
        </Grid>
      </Grid>
    </>
  );
};

export default DomainUsersPanel;
