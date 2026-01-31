import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import Papa from 'papaparse';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  Drawer,
  FormControl,
  Grid,
  IconButton,
  InputAdornment,
  InputLabel,
  LinearProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  MenuItem,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery,
  useTheme
} from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  Add as AddIcon,
  AdminPanelSettings as AdminIcon,
  BugReport as BugReportIcon,
  Build as BuildIcon,
  Delete as DeleteIcon,
  Download as DownloadIcon,
  Menu as MenuIcon,
  Password as PasswordIcon,
  People as PeopleIcon,
  PersonAdd as PersonAddIcon,
  Refresh as RefreshIcon,
  Save as SaveIcon,
  Search as SearchIcon,
  Security as SecurityIcon,
  Storage as StorageIcon,
  VpnKey as VpnKeyIcon,
  Warning as WarningIcon
} from '@mui/icons-material';

const MIN_PASSWORD_LENGTH = 12;
const MAX_PASSWORD_LENGTH = 64;
const COMMON_PASSWORDS = new Set([
  'password', 'password1', '123456', '12345678', '123456789',
  'qwerty', 'qwerty123', 'letmein', 'welcome', 'admin',
  'admin123', 'iloveyou', 'monkey', 'dragon', 'football',
  'abc123', '111111', 'trustno1', 'sunshine', 'princess',
  'login', 'qwertyuiop', 'passw0rd', 'master', 'shadow'
]);

const drawerWidth = 280;

const AdminSettings = ({ darkMode }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [selectedUserRoles, setSelectedUserRoles] = useState({});
  const [existingUsers, setExistingUsers] = useState([]);
  const [editedUserRoles, setEditedUserRoles] = useState({});
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('');
  const [loading, setLoading] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [retypePassword, setRetypePassword] = useState('');

  const [sourceTypes, setSourceTypes] = useState([]);
  const [ipsBySource, setIpsBySource] = useState({});
  const [selectedSource, setSelectedSource] = useState('');
  const [newSourceName, setNewSourceName] = useState('');
  const [newIpAddress, setNewIpAddress] = useState('');
  const [ipsToAdd, setIpsToAdd] = useState([]);
  const [ipsToDelete, setIpsToDelete] = useState([]);

  const [localUsername, setLocalUsername] = useState('');
  const [localRole, setLocalRole] = useState('user');
  const [localTempPassword, setLocalTempPassword] = useState('');

  const [vulnCategories, setVulnCategories] = useState([]);
  const [newCategoryName, setNewCategoryName] = useState('');

  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetPhrase, setResetPhrase] = useState('');
  const [resetConfirmChecked, setResetConfirmChecked] = useState(false);
  const [resetStats, setResetStats] = useState(null);
  const [resetSummary, setResetSummary] = useState(null);
  const [resetCsv, setResetCsv] = useState('');

  const [selectedSection, setSelectedSection] = useState('users');
  const [navOpen, setNavOpen] = useState(false);

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  const sections = useMemo(() => ([
    {
      key: 'users',
      label: 'User Management',
      description: 'Manage existing users, roles, and access types.',
      icon: PeopleIcon
    },
    {
      key: 'add-users',
      label: 'Add Domain Users',
      description: 'Search LDAP and add new users to the platform.',
      icon: PersonAddIcon
    },
    {
      key: 'local-users',
      label: 'Local Users',
      description: 'Create local accounts for offline access.',
      icon: AdminIcon
    },
    {
      key: 'security',
      label: 'Security',
      description: 'Update the admin password and security settings.',
      icon: SecurityIcon
    },
    {
      key: 'ip-sources',
      label: 'IP Sources',
      description: 'Map IP addresses to source groups used in asset tracking.',
      icon: StorageIcon
    },
    {
      key: 'vuln-categories',
      label: 'Vulnerability Categories',
      description: 'Manage the vulnerability taxonomy used in pentest reports.',
      icon: BugReportIcon
    },
    {
      key: 'maintenance',
      label: 'Maintenance',
      description: 'Run manual updates and manage pentest resets.',
      icon: BuildIcon
    }
  ]), []);

  const activeSection = sections.find((section) => section.key === selectedSection) || sections[0];

  const validatePassword = (value) => {
    if (!value) return 'New password is required.';
    if (value.length < MIN_PASSWORD_LENGTH) {
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (value.length > MAX_PASSWORD_LENGTH) {
      return `Password must be at most ${MAX_PASSWORD_LENGTH} characters.`;
    }
    if (COMMON_PASSWORDS.has(value.trim().toLowerCase())) {
      return 'Password is too common.';
    }
    return '';
  };
  useEffect(() => {
    fetchIpSources();
    fetchExistingUsers();
    fetchVulnCategories();
  }, []);

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const showMessage = (type, text) => {
    setMessageType(type);
    setMessage(text);
  };

  const fetchIpSources = async () => {
    try {
      const response = await axios.get('/ip-sources');
      if (response.status === 200 && response.data.ip_sources) {
        const map = {};
        response.data.ip_sources.forEach((item) => {
          map[item.source_name] = map[item.source_name] || [];
          map[item.source_name].push(item.ip_address);
        });
        setSourceTypes(Array.from(new Set(response.data.ip_sources.map((item) => item.source_name))));
        setIpsBySource(map);
      }
    } catch (error) {
      showMessage('error', 'Failed to fetch IP sources.');
      console.error(error);
    }
  };

  const handleAddSourceType = () => {
    const trimmedName = newSourceName.trim();
    if (!trimmedName || sourceTypes.includes(trimmedName)) {
      showMessage('error', sourceTypes.includes(trimmedName) ? 'This source type already exists.' : 'Invalid source name.');
      return;
    }
    setSourceTypes([...sourceTypes, trimmedName]);
    setIpsBySource({ ...ipsBySource, [trimmedName]: [] });
    setSelectedSource(trimmedName);
    setNewSourceName('');
  };

  const handleSelectSourceType = (srcName) => {
    setSelectedSource(srcName);
    setIpsToAdd([]);
    setIpsToDelete([]);
    setNewIpAddress('');
  };

  const handleAddIp = () => {
    const trimmedIp = newIpAddress.trim();
    if (!trimmedIp || !selectedSource) return;
    const currentIps = ipsBySource[selectedSource] || [];
    if (currentIps.includes(trimmedIp)) {
      showMessage('error', 'IP already exists in this source.');
      return;
    }
    setIpsBySource({ ...ipsBySource, [selectedSource]: [...currentIps, trimmedIp] });
    setIpsToAdd([...ipsToAdd, trimmedIp]);
    setNewIpAddress('');
  };

  const handleDeleteIpClick = (ip) => {
    if (!ipsToDelete.includes(ip)) setIpsToDelete([...ipsToDelete, ip]);
    setIpsBySource({
      ...ipsBySource,
      [selectedSource]: (ipsBySource[selectedSource] || []).filter((x) => x !== ip)
    });
  };

  const handleSubmitChanges = async () => {
    if (!selectedSource) return;
    setLoading(true);
    try {
      await Promise.all([
        ...ipsToAdd.map((ip) => axios.post('/ip-sources', { source_name: selectedSource, ip_address: ip })),
        ...ipsToDelete.map((ip) => axios.delete('/ip-sources', { data: { ip_address: ip } }))
      ]);
      showMessage('success', 'Changes submitted successfully.');
      setIpsToAdd([]);
      setIpsToDelete([]);
      fetchIpSources();
    } catch (error) {
      console.error('Failed to submit changes', error);
      showMessage('error', 'Failed to submit changes.');
    } finally {
      setLoading(false);
    }
  };
  const handleSelectUser = (user) => {
    if (!selectedUsers.some((selected) => selected.username === user.username)) {
      setSelectedUsers([...selectedUsers, user]);
      setSearchResults(searchResults.filter((result) => result.username !== user.username));
      setSelectedUserRoles({ ...selectedUserRoles, [user.username]: 'user' });
    }
  };

  const handleRemoveUser = (user) => {
    setSearchResults([...searchResults, user]);
    setSelectedUsers(selectedUsers.filter((selected) => selected.username !== user.username));
    const { [user.username]: removedRole, ...restRoles } = selectedUserRoles;
    setSelectedUserRoles(restRoles);
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const usersWithRoles = selectedUsers.map((user) => ({
        username: user.username,
        email: user.email,
        role: selectedUserRoles[user.username] || 'user'
      }));
      const responses = await Promise.all(usersWithRoles.map((user) => axios.post('/add-user', user)));
      if (responses.every((response) => response.status === 200)) {
        showMessage('success', 'Users added successfully.');
        setSelectedUsers([]);
        setSelectedUserRoles({});
        fetchExistingUsers();
      }
    } catch (error) {
      showMessage('error', 'Failed to add users. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveRole = async (username, newRole) => {
    try {
      const response = await axios.post('/update-user-role', { username, role: newRole });
      if (response.status === 200) {
        setExistingUsers((prevUsers) => prevUsers.map((user) =>
          user.username === username ? { ...user, role: newRole } : user
        ));
        showMessage('success', response.data.message);
      } else {
        showMessage('error', 'Failed to update role. Please try again.');
      }
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to update user role. Please try again.');
    }
  };

  const handleDeleteUser = async (username) => {
    if (!window.confirm(`Are you sure you want to delete user ${username}?`)) return;
    try {
      const response = await axios.delete('/delete-user', { data: { username } });
      if (response.status === 200) {
        showMessage('success', `User ${username} deleted successfully.`);
        setExistingUsers(existingUsers.filter((user) => user.username !== username));
      }
    } catch (error) {
      showMessage('error', `Failed to delete user ${username}.`);
    }
  };

  const handleSearch = async () => {
    setLoading(true);
    try {
      setSearchResults([]);
      const response = await axios.get(`/ldap-search?query=${searchQuery}`);
      if (response.status === 200) {
        setSearchResults(response.data.results.filter((user) =>
          user.username !== 'None' && user.email !== 'None' && user.full_name !== 'None'
        ));
      } else {
        showMessage('error', 'No results found.');
      }
    } catch (error) {
      showMessage('error', 'Error searching LDAP. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const fetchExistingUsers = async () => {
    try {
      const response = await axios.get('/existing-users');
      if (response.status === 200) setExistingUsers(response.data.users);
    } catch (error) {
      showMessage('error', 'Failed to fetch existing users.');
    }
  };

  const handleManualParse = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/manual-update');
      if (response.status === 200) {
        showMessage('success', 'Records updated successfully.');
      }
    } catch (error) {
      showMessage('error', 'Failed to parse records. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  const fetchVulnCategories = async () => {
    try {
      const response = await axios.get('/vuln-categories');
      if (response.status === 200) {
        setVulnCategories(response.data.categories || []);
      }
    } catch (error) {
      showMessage('error', 'Failed to fetch vulnerability categories.');
    }
  };

  const handleAddVulnCategory = async () => {
    const name = newCategoryName.trim();
    if (!name) {
      showMessage('error', 'Category name is required.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/vuln-categories', { name });
      if (response.status === 200) {
        showMessage('success', 'Category added successfully.');
        setNewCategoryName('');
        fetchVulnCategories();
      }
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to add category.');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteVulnCategory = async (categoryId) => {
    if (!window.confirm('Delete this category?')) return;
    setLoading(true);
    try {
      const response = await axios.delete(`/vuln-categories/${categoryId}`);
      if (response.status === 200) {
        showMessage('success', 'Category deleted successfully.');
        fetchVulnCategories();
      }
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to delete category.');
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async () => {
    const validationError = validatePassword(newPassword);
    if (validationError) {
      showMessage('error', validationError);
      return;
    }
    if (newPassword !== retypePassword) {
      showMessage('error', 'New password and retyped password do not match.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/change-password', {
        current_password: currentPassword,
        new_password: newPassword
      });
      if (response.status === 200) {
        showMessage('success', 'Password changed successfully.');
        setCurrentPassword('');
        setNewPassword('');
        setRetypePassword('');
      }
    } catch (error) {
      showMessage('error', 'Failed to change password. Please check your current password.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateLocalUser = async () => {
    const trimmedUsername = localUsername.trim().toLowerCase();
    if (!trimmedUsername) {
      showMessage('error', 'Local username is required.');
      return;
    }
    if (!['user', 'pentester'].includes(localRole)) {
      showMessage('error', 'Invalid role specified.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/add-local-user', {
        username: trimmedUsername,
        role: localRole
      });
      if (response.status === 200) {
        showMessage('success', "Local user  created. Temporary password generated.");
        setLocalTempPassword(response.data.temp_password || '');
        setLocalUsername('');
        setLocalRole('user');
        fetchExistingUsers();
      }
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to create local user.');
    } finally {
      setLoading(false);
    }
  };

  const requiredResetPhrase = 'RESET ALL BUT OPEN VULNERABILITIES';

  const handleOpenResetDialog = () => {
    setResetDialogOpen(true);
    setResetPhrase('');
    setResetConfirmChecked(false);
    fetchResetSummary();
  };

  const handleCloseResetDialog = () => {
    setResetDialogOpen(false);
  };

  const buildResetSummary = (data) => ({
    total: data.length,
    completed: data.filter((r) => r.status === 'Completed').length,
    inProgress: data.filter((r) => r.status === 'In Progress').length,
    notStarted: data.filter((r) => !r.status || r.status === 'Not Started').length,
    vulnerable: data.filter((r) => r.vulnerable === 1).length,
    fixed: data.filter((r) => r.vulnerability_fixed === 1).length,
    open: data.filter((r) => r.vulnerable === 1 && r.vulnerability_fixed === 0).length,
    reports: data.filter((r) => r.report_file).length
  });

  const buildResetCsv = (data) => Papa.unparse(data.map((item) => ({
    'Target Name': item.name,
    'IP Address': item.ip_address,
    'Source': item.source,
    'Status': item.status,
    'Vulnerable': item.vulnerable === 1 ? 'Yes' : 'No',
    'Tested By': item.tested_by,
    'Start Date': item.test_start_date,
    'End Date': item.test_end_date,
    'Fixed': item.vulnerability_fixed === 1 ? 'Yes' : 'No',
    'Service Desk': item.service_desk_link,
    'Report': item.report_file ? 'Yes' : 'No'
  })));

  const fetchResetSummary = async () => {
    try {
      const response = await axios.get('/pentest/records');
      if (response.status === 200) {
        const data = response.data || [];
        setResetSummary(buildResetSummary(data));
        setResetCsv(buildResetCsv(data));
      }
    } catch (error) {
      showMessage('error', 'Failed to load pentest summary.');
    }
  };

  const downloadResetCsv = () => {
    if (!resetCsv) return;
    const blob = new Blob([resetCsv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'pentest_yearly_summary.csv');
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleResetOpenVulnerabilities = async () => {
    if (!resetConfirmChecked || resetPhrase !== requiredResetPhrase) {
      showMessage('error', 'Please confirm the reset phrase to proceed.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/pentest/reset-keep-open', {
        confirm: true,
        phrase: resetPhrase
      });
      if (response.status === 200) {
        setResetStats(response.data.stats || null);
        showMessage('success', 'Pentest progress reset successfully (open vulnerabilities preserved).');
        handleCloseResetDialog();
      }
    } catch (error) {
      showMessage('error', error.response?.data?.error || 'Failed to reset pentest progress.');
    } finally {
      setLoading(false);
    }
  };

  const getAuthChip = (authType) => {
    const normalized = (authType || 'ldap').toLowerCase();
    const configs = {
      local: { label: 'Local', color: theme.palette.warning.main },
      ldap: { label: 'LDAP', color: theme.palette.info.main }
    };
    const config = configs[normalized] || configs.ldap;

    return (
      <Chip
        label={config.label}
        size="small"
        sx={{
          backgroundColor: alpha(config.color, 0.1),
          color: config.color,
          fontWeight: 600
        }}
      />
    );
  };

  const drawerContent = (
    <Box sx={{ width: drawerWidth }}>
      <Box sx={theme.mixins.toolbar} />
      <Box sx={{ px: 2.5, py: 2 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Admin Settings
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Select a section to manage
        </Typography>
      </Box>
      <Divider />
      <List sx={{ px: 1 }}>
        {sections.map((section) => (
          <ListItemButton
            key={section.key}
            selected={selectedSection === section.key}
            onClick={() => {
              setSelectedSection(section.key);
              if (isMobile) setNavOpen(false);
            }}
            sx={{
              borderRadius: 1,
              mb: 0.5,
              '&.Mui-selected': {
                backgroundColor: alpha(theme.palette.primary.main, 0.12)
              },
              '&.Mui-selected:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.18)
              }
            }}
          >
            <ListItemIcon sx={{ minWidth: 40 }}>
              <section.icon fontSize="small" />
            </ListItemIcon>
            <ListItemText
              primary={section.label}
              primaryTypographyProps={{ fontSize: '0.95rem', fontWeight: 600 }}
            />
          </ListItemButton>
        ))}
      </List>
    </Box>
  );
  const renderUserManagement = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <PeopleIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            User Management
          </Typography>
          <Chip
            label={`${existingUsers.length} users`}
            size="small"
            sx={{
              ml: 2,
              backgroundColor: alpha(theme.palette.info.main, 0.1),
              color: theme.palette.info.main
            }}
          />
        </Box>

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
            {existingUsers.map((user) => (
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
                        value={editedUserRoles[user.username] || user.role}
                        onChange={(e) => {
                          const newRole = e.target.value;
                          setEditedUserRoles({ ...editedUserRoles, [user.username]: newRole });
                          handleSaveRole(user.username, newRole);
                        }}
                        size="small"
                      >
                        <MenuItem value="user">User</MenuItem>
                        <MenuItem value="pentester">Pentester</MenuItem>
                      </Select>
                    </FormControl>

                    <Tooltip title="Delete User">
                      <IconButton
                        color="error"
                        onClick={() => handleDeleteUser(user.username)}
                        size="small"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  </Box>

                  <Box mt={1}>
                    {getAuthChip(user.auth_type)}
                  </Box>
                </Paper>
              </Grid>
            ))}
          </Grid>
        )}
      </CardContent>
    </Card>
  );

  const renderAddDomainUsers = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <PersonAddIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Add Domain Users
          </Typography>
        </Box>

        <Box display="flex" gap={1} mb={2}>
          <TextField
            placeholder="Search domain user..."
            variant="outlined"
            size="small"
            fullWidth
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
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
            onClick={handleSearch}
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
                    .filter((user) => !existingUsers.some((u) => u.username === user.username))
                    .map((user) => (
                      <ListItem
                        key={user.username}
                        button
                        onClick={() => handleSelectUser(user)}
                        sx={{
                          borderRadius: 1,
                          mb: 0.5,
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
                  {selectedUsers.map((user) => (
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
                          <FormControl size="small" sx={{ mt: 0.5, minWidth: 80 }}>
                            <Select
                              value={selectedUserRoles[user.username] || 'user'}
                              onChange={(e) => setSelectedUserRoles({
                                ...selectedUserRoles,
                                [user.username]: e.target.value
                              })}
                              size="small"
                            >
                              <MenuItem value="user">User</MenuItem>
                              <MenuItem value="pentester">Pentester</MenuItem>
                            </Select>
                          </FormControl>
                        }
                        primaryTypographyProps={{ fontSize: '0.875rem' }}
                      />
                      <IconButton
                        edge="end"
                        color="error"
                        onClick={() => handleRemoveUser(user)}
                        size="small"
                      >
                        <DeleteIcon />
                      </IconButton>
                    </ListItem>
                  ))}
                </List>
              )}
              {selectedUsers.length > 0 && (
                <Button
                  variant="contained"
                  color="secondary"
                  startIcon={<PersonAddIcon />}
                  onClick={handleSubmit}
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
      </CardContent>
    </Card>
  );
  const renderLocalUsers = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <AdminIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Create Local User
          </Typography>
        </Box>

        <Stack spacing={2}>
          <TextField
            label="Username"
            variant="outlined"
            fullWidth
            value={localUsername}
            onChange={(e) => setLocalUsername(e.target.value)}
            placeholder="local.user"
          />
          <FormControl fullWidth size="small">
            <InputLabel id="local-user-role-label">Role</InputLabel>
            <Select
              labelId="local-user-role-label"
              value={localRole}
              label="Role"
              onChange={(e) => setLocalRole(e.target.value)}
            >
              <MenuItem value="user">User</MenuItem>
              <MenuItem value="pentester">Pentester</MenuItem>
            </Select>
          </FormControl>
          <Button
            variant="contained"
            startIcon={<PersonAddIcon />}
            onClick={handleCreateLocalUser}
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
      </CardContent>
    </Card>
  );

  const renderSecurity = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <SecurityIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Security Settings
          </Typography>
        </Box>

        <Stack spacing={2}>
          <TextField
            label="Current Password"
            type="password"
            variant="outlined"
            fullWidth
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <VpnKeyIcon />
                </InputAdornment>
              )
            }}
          />
          <TextField
            label="New Password"
            type="password"
            variant="outlined"
            fullWidth
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <PasswordIcon />
                </InputAdornment>
              )
            }}
          />
          <TextField
            label="Confirm New Password"
            type="password"
            variant="outlined"
            fullWidth
            value={retypePassword}
            onChange={(e) => setRetypePassword(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <PasswordIcon />
                </InputAdornment>
              )
            }}
          />
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
              NIST password requirements:
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block">
              - At least {MIN_PASSWORD_LENGTH} characters (max {MAX_PASSWORD_LENGTH})
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block">
              - Not a common password
            </Typography>
          </Box>
          <Button
            variant="contained"
            size="large"
            startIcon={<SecurityIcon />}
            onClick={handleChangePassword}
            disabled={loading}
            sx={{ mt: 2 }}
          >
            Update Password
          </Button>
        </Stack>
      </CardContent>
    </Card>
  );

  const renderIpSources = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <StorageIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            IP Sources
          </Typography>
        </Box>

        <Grid container spacing={3}>
          <Grid item xs={12} md={4}>
            <Paper sx={{ p: 2, backgroundColor: 'background.default' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
                Source Groups
              </Typography>

              <Stack spacing={1.5}>
                <TextField
                  size="small"
                  label="New Source Name"
                  value={newSourceName}
                  onChange={(e) => setNewSourceName(e.target.value)}
                />
                <Button
                  variant="contained"
                  startIcon={<AddIcon />}
                  onClick={handleAddSourceType}
                  disabled={!newSourceName.trim()}
                >
                  Add Source
                </Button>
              </Stack>

              <Divider sx={{ my: 2 }} />

              {sourceTypes.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  No sources yet.
                </Typography>
              ) : (
                <List dense sx={{ maxHeight: 260, overflow: 'auto' }}>
                  {sourceTypes.map((source) => (
                    <ListItemButton
                      key={source}
                      selected={selectedSource === source}
                      onClick={() => handleSelectSourceType(source)}
                      sx={{ borderRadius: 1 }}
                    >
                      <ListItemText primary={source} />
                    </ListItemButton>
                  ))}
                </List>
              )}
            </Paper>
          </Grid>

          <Grid item xs={12} md={8}>
            <Paper sx={{ p: 2, backgroundColor: 'background.default' }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
                IP Addresses
              </Typography>

              {!selectedSource ? (
                <Typography variant="body2" color="text.secondary">
                  Select a source group to manage IPs.
                </Typography>
              ) : (
                <>
                  <Box display="flex" gap={1} mb={2}>
                    <TextField
                      size="small"
                      label="Add IP Address"
                      value={newIpAddress}
                      onChange={(e) => setNewIpAddress(e.target.value)}
                      fullWidth
                    />
                    <Button
                      variant="contained"
                      startIcon={<AddIcon />}
                      onClick={handleAddIp}
                    >
                      Add
                    </Button>
                  </Box>

                  <Box sx={{ maxHeight: 240, overflow: 'auto' }}>
                    {(ipsBySource[selectedSource] || []).length === 0 ? (
                      <Typography variant="body2" color="text.secondary">
                        No IPs for this source yet.
                      </Typography>
                    ) : (
                      <List dense>
                        {(ipsBySource[selectedSource] || []).map((ip) => (
                          <ListItem
                            key={ip}
                            secondaryAction={
                              <IconButton
                                edge="end"
                                color="error"
                                onClick={() => handleDeleteIpClick(ip)}
                                size="small"
                              >
                                <DeleteIcon />
                              </IconButton>
                            }
                          >
                            <ListItemText primary={ip} />
                          </ListItem>
                        ))}
                      </List>
                    )}
                  </Box>

                  <Divider sx={{ my: 2 }} />

                  <Button
                    variant="contained"
                    startIcon={<SaveIcon />}
                    onClick={handleSubmitChanges}
                    disabled={loading}
                    fullWidth
                  >
                    Submit Changes
                  </Button>
                </>
              )}
            </Paper>
          </Grid>
        </Grid>
      </CardContent>
    </Card>
  );
  const renderVulnCategories = () => (
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={3}>
          <BugReportIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Vulnerability Categories
          </Typography>
        </Box>

        <Box display="flex" gap={1} mb={2}>
          <TextField
            fullWidth
            size="small"
            placeholder="Add new category"
            value={newCategoryName}
            onChange={(e) => setNewCategoryName(e.target.value)}
          />
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={handleAddVulnCategory}
            disabled={loading}
          >
            Add
          </Button>
        </Box>

        {vulnCategories.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No categories found.
          </Typography>
        ) : (
          <List sx={{ maxHeight: 300, overflow: 'auto' }}>
            {vulnCategories.map((category) => (
              <ListItem
                key={category.id}
                secondaryAction={
                  <IconButton
                    edge="end"
                    color="error"
                    onClick={() => handleDeleteVulnCategory(category.id)}
                    size="small"
                  >
                    <DeleteIcon />
                  </IconButton>
                }
              >
                <ListItemText
                  primary={category.name}
                  secondary={category.is_custom ? 'Custom' : 'Default'}
                />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );

  const renderMaintenance = () => (
    <Stack spacing={3}>
      <Card>
        <CardContent>
          <Box display="flex" alignItems="center" mb={2}>
            <RefreshIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Manual Update
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Trigger a manual parse of DNS zone files and refresh asset records.
          </Typography>
          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            onClick={handleManualParse}
            disabled={loading}
          >
            Run Update
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Box display="flex" alignItems="center" mb={2}>
            <WarningIcon sx={{ color: theme.palette.warning.main, mr: 1 }} />
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              Pentest Reset
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Reset pentest progress for all records except open vulnerabilities.
          </Typography>

          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              onClick={downloadResetCsv}
              disabled={!resetCsv}
            >
              Download Summary CSV
            </Button>
            <Button
              variant="contained"
              color="warning"
              startIcon={<WarningIcon />}
              onClick={handleOpenResetDialog}
            >
              Reset Pentest Progress
            </Button>
          </Stack>

          {resetStats && (
            <Alert severity="info" sx={{ mt: 2 }}>
              Reset completed. {resetStats.total_reset} records cleared, {resetStats.remaining_open} open vulnerabilities preserved.
            </Alert>
          )}
        </CardContent>
      </Card>
    </Stack>
  );
  const renderSection = () => {
    switch (selectedSection) {
      case 'users':
        return renderUserManagement();
      case 'add-users':
        return renderAddDomainUsers();
      case 'local-users':
        return renderLocalUsers();
      case 'security':
        return renderSecurity();
      case 'ip-sources':
        return renderIpSources();
      case 'vuln-categories':
        return renderVulnCategories();
      case 'maintenance':
        return renderMaintenance();
      default:
        return renderUserManagement();
    }
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: 'background.default' }}>
      <Drawer
        variant={isMobile ? 'temporary' : 'permanent'}
        open={isMobile ? navOpen : true}
        onClose={() => setNavOpen(false)}
        ModalProps={{ keepMounted: true }}
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            borderRight: `1px solid ${theme.palette.divider}`
          }
        }}
      >
        {drawerContent}
      </Drawer>

      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Box display="flex" alignItems="center" gap={2} mb={3}>
          {isMobile && (
            <IconButton onClick={() => setNavOpen(true)}>
              <MenuIcon />
            </IconButton>
          )}
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 600 }}>
              {activeSection.label}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {activeSection.description}
            </Typography>
          </Box>
        </Box>

        {loading && (
          <LinearProgress sx={{ mb: 2 }} />
        )}

        <Collapse in={Boolean(message)}>
          <Alert
            severity={messageType || 'info'}
            sx={{ mb: 2 }}
            onClose={() => setMessage('')}
          >
            {message}
          </Alert>
        </Collapse>

        {renderSection()}
      </Box>

      <Dialog open={resetDialogOpen} onClose={handleCloseResetDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Confirm Pentest Progress Refresh</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This will remove pentest progress for every record except open vulnerabilities.
            Please export the summary if needed.
          </Alert>

          {resetSummary && (
            <Paper sx={{ p: 2, mb: 2, backgroundColor: 'background.default' }}>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">Total Records</Typography>
                  <Typography variant="subtitle2">{resetSummary.total}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">Completed</Typography>
                  <Typography variant="subtitle2">{resetSummary.completed}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">In Progress</Typography>
                  <Typography variant="subtitle2">{resetSummary.inProgress}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">Open Vulnerabilities</Typography>
                  <Typography variant="subtitle2">{resetSummary.open}</Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="caption" color="text.secondary">Reports</Typography>
                  <Typography variant="subtitle2">{resetSummary.reports}</Typography>
                </Grid>
              </Grid>
            </Paper>
          )}

          <TextField
            label="Confirmation Phrase"
            fullWidth
            value={resetPhrase}
            onChange={(e) => setResetPhrase(e.target.value)}
            placeholder={requiredResetPhrase}
            sx={{ mb: 2 }}
          />

          <Paper sx={{ p: 2, backgroundColor: alpha(theme.palette.warning.main, 0.08) }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              Type the phrase above and confirm the checkbox to continue.
            </Typography>
            <Box display="flex" alignItems="center" gap={1} mt={1}>
              <input
                type="checkbox"
                checked={resetConfirmChecked}
                onChange={(e) => setResetConfirmChecked(e.target.checked)}
              />
              <Typography variant="body2">
                I understand this action cannot be undone.
              </Typography>
            </Box>
          </Paper>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseResetDialog}>Cancel</Button>
          <Button
            variant="contained"
            color="warning"
            startIcon={<WarningIcon />}
            onClick={handleResetOpenVulnerabilities}
            disabled={loading}
          >
            Confirm Reset
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AdminSettings;
