import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Papa from 'papaparse';
import { 
  TextField, 
  Button, 
  Box, 
  Typography, 
  Paper, 
  List, 
  ListItem, 
  ListItemText, 
  IconButton,
  Card,
  CardContent,
  Grid,
  useTheme,
  alpha,
  Divider,
  Chip,
  Avatar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Checkbox,
  FormControlLabel,
  Stack,
  Tooltip,
  LinearProgress,
  InputAdornment
} from '@mui/material';
import {
  Delete as DeleteIcon,
  Settings as SettingsIcon,
  Storage as StorageIcon,
  Security as SecurityIcon,
  People as PeopleIcon,
  Search as SearchIcon,
  Add as AddIcon,
  Save as SaveIcon,
  VpnKey as VpnKeyIcon,
  Computer as ComputerIcon,
  Refresh as RefreshIcon,
  AdminPanelSettings as AdminIcon,
  PersonAdd as PersonAddIcon,
  Edit as EditIcon,
  Password as PasswordIcon,
  Warning as WarningIcon,
  Download as DownloadIcon
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

const AdminSettings = ({ darkMode }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [message, setMessage] = useState('');
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [messageType, setMessageType] = useState('');
  const [existingUsers, setExistingUsers] = useState([]);
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
  const [selectedUserRoles, setSelectedUserRoles] = useState({});
  const [editedUserRoles, setEditedUserRoles] = useState({});
  const [loading, setLoading] = useState(false);
  const [localUsername, setLocalUsername] = useState('');
  const [localRole, setLocalRole] = useState('user');
  const [localTempPassword, setLocalTempPassword] = useState('');
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [resetPhrase, setResetPhrase] = useState('');
  const [resetConfirmChecked, setResetConfirmChecked] = useState(false);
  const [resetStats, setResetStats] = useState(null);
  const [resetSummary, setResetSummary] = useState(null);
  const [resetCsv, setResetCsv] = useState('');
  
  const theme = useTheme();

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
  }, []);

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const fetchIpSources = async () => {
    try {
      const response = await axios.get('/ip-sources');
      if (response.status === 200 && response.data.ip_sources) {
        const map = {};
        response.data.ip_sources.forEach(item => { 
          map[item.source_name] = map[item.source_name] || []; 
          map[item.source_name].push(item.ip_address); 
        });
        setSourceTypes(Array.from(new Set(response.data.ip_sources.map(item => item.source_name))));
        setIpsBySource(map);
      }
    } catch (error) { 
      setMessageType('error'); 
      setMessage('Failed to fetch IP sources.'); 
      console.error(error); 
    }
  };

  const handleAddSourceType = () => {
    const trimmedName = newSourceName.trim();
    if (!trimmedName || sourceTypes.includes(trimmedName)) {
      setMessageType('error');
      setMessage(sourceTypes.includes(trimmedName) ? 'This source type already exists.' : 'Invalid source name.');
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
      setMessageType('error'); 
      setMessage('IP already exists in this source.'); 
      return;
    }
    setIpsBySource({ ...ipsBySource, [selectedSource]: [...currentIps, trimmedIp] });
    setIpsToAdd([...ipsToAdd, trimmedIp]);
    setNewIpAddress('');
  };

  const handleDeleteIpClick = (ip) => {
    if (!ipsToDelete.includes(ip)) setIpsToDelete([...ipsToDelete, ip]);
    setIpsBySource({ ...ipsBySource, [selectedSource]: (ipsBySource[selectedSource] || []).filter(x => x !== ip) });
  };

  const handleSubmitChanges = async () => {
    if (!selectedSource) return;
    setLoading(true);
    try {
      await Promise.all([
        ...ipsToAdd.map(ip => axios.post('/ip-sources', { source_name: selectedSource, ip_address: ip })), 
        ...ipsToDelete.map(ip => axios.delete('/ip-sources', { data: { ip_address: ip } }))
      ]);
      setMessageType('success'); 
      setMessage('Changes submitted successfully.');
      setIpsToAdd([]); 
      setIpsToDelete([]); 
      fetchIpSources();
    } catch (error) {
      console.error('Failed to submit changes', error);
      setMessageType('error');
      setMessage('Failed to submit changes.');
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
      const usersWithRoles = selectedUsers.map(user => ({ 
        username: user.username, 
        email: user.email, 
        role: selectedUserRoles[user.username] || 'user' 
      }));
      const responses = await Promise.all(usersWithRoles.map(user => axios.post('/add-user', user)));
      if (responses.every(response => response.status === 200)) {
        setMessageType('success'); 
        setMessage('Users added successfully.'); 
        setSelectedUsers([]); 
        setSelectedUserRoles({});
        setTimeout(() => { window.location.reload(); }, 1000);
      }
    } catch (error) {
      setMessageType('error'); 
      setMessage('Failed to add users. Please try again.');
    } finally { 
      setLoading(false);
    }
  };

  const handleSaveRole = async (username, newRole) => {
    try {
      const response = await axios.post('/update-user-role', { username, role: newRole });
      if (response.status === 200) {
        setExistingUsers(prevUsers => prevUsers.map(user => 
          user.username === username ? { ...user, role: newRole } : user
        ));
        setMessageType('success');
        setMessage(response.data.message);
      } else {
        setMessageType('error');
        setMessage('Failed to update role. Please try again.');
      }
    } catch (error) {
      setMessageType('error');
      setMessage(error.response?.data?.error || 'Failed to update user role. Please try again.');
    }
  };

  const handleDeleteUser = async (username) => {
    if (!window.confirm(`Are you sure you want to delete user ${username}?`)) return;
    try {
      const response = await axios.delete('/delete-user', { data: { username } });
      if (response.status === 200) {
        setMessageType('success'); 
        setMessage(`User ${username} deleted successfully.`); 
        setExistingUsers(existingUsers.filter((user) => user.username !== username));
      }
    } catch (error) {
      setMessageType('error'); 
      setMessage(`Failed to delete user ${username}.`);
    }
  };

  const handleManualParse = async () => {
    setLoading(true);
    try {
      const response = await axios.post('/manual-update');
      if (response.status === 200) { 
        setMessageType('success'); 
        setMessage('Records updated successfully.'); 
      }
    } catch (error) {
      setMessageType('error'); 
      setMessage('Failed to parse records. Please try again.');
    } finally { 
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    setLoading(true);
    try {
      setSearchResults([]);
      const response = await axios.get(`/ldap-search?query=${searchQuery}`);
      if (response.status === 200) {
        setSearchResults(response.data.results.filter(user => 
          user.username !== "None" && user.email !== "None" && user.full_name !== "None"
        ));
      } else { 
        setMessageType('error'); 
        setMessage('No results found.'); 
      }
    } catch (error) {
      setMessageType('error'); 
      setMessage('Error searching LDAP. Please try again.');
    } finally { 
      setLoading(false);
    }
  };

  const fetchExistingUsers = async () => {
    try {
      const response = await axios.get('/existing-users');
      if (response.status === 200) setExistingUsers(response.data.users);
    } catch (error) {
      setMessageType('error'); 
      setMessage('Failed to fetch existing users.');
    }
  };

  const handleChangePassword = async () => {
    const validationError = validatePassword(newPassword);
    if (validationError) {
      setMessageType('error');
      setMessage(validationError);
      return;
    }
    if (newPassword !== retypePassword) {
      setMessageType('error'); 
      setMessage('New password and retyped password do not match.'); 
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/change-password', { 
        current_password: currentPassword, 
        new_password: newPassword 
      });
      if (response.status === 200) {
        setMessageType('success'); 
        setMessage('Password changed successfully.'); 
        setCurrentPassword(''); 
        setNewPassword(''); 
        setRetypePassword('');
      }
    } catch (error) {
      setMessageType('error'); 
      setMessage('Failed to change password. Please check your current password.');
    } finally { 
      setLoading(false);
    }
  };

  const handleCreateLocalUser = async () => {
    const trimmedUsername = localUsername.trim().toLowerCase();
    if (!trimmedUsername) {
      setMessageType('error');
      setMessage('Local username is required.');
      return;
    }
    if (!['user', 'pentester'].includes(localRole)) {
      setMessageType('error');
      setMessage('Invalid role specified.');
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/add-local-user', {
        username: trimmedUsername,
        role: localRole
      });
      if (response.status === 200) {
        setMessageType('success');
        setMessage(`Local user ${trimmedUsername} created. Temporary password generated.`);
        setLocalTempPassword(response.data.temp_password || '');
        setLocalUsername('');
        setLocalRole('user');
        fetchExistingUsers();
      }
    } catch (error) {
      setMessageType('error');
      setMessage(error.response?.data?.error || 'Failed to create local user.');
    } finally {
      setLoading(false);
    }
  };

  const requiredResetPhrase = "RESET ALL BUT OPEN VULNERABILITIES";

  const handleOpenResetDialog = () => {
    setResetDialogOpen(true);
    setResetPhrase('');
    setResetConfirmChecked(false);
    fetchResetSummary();
  };

  const handleCloseResetDialog = () => {
    setResetDialogOpen(false);
  };

  const buildResetSummary = (data) => {
    const summary = {
      total: data.length,
      completed: data.filter((r) => r.status === 'Completed').length,
      inProgress: data.filter((r) => r.status === 'In Progress').length,
      notStarted: data.filter((r) => !r.status || r.status === 'Not Started').length,
      vulnerable: data.filter((r) => r.vulnerable === 1).length,
      fixed: data.filter((r) => r.vulnerability_fixed === 1).length,
      open: data.filter((r) => r.vulnerable === 1 && r.vulnerability_fixed === 0).length,
      reports: data.filter((r) => r.report_file).length
    };
    return summary;
  };

  const buildResetCsv = (data) => Papa.unparse(data.map(item => ({
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
      setMessageType('error');
      setMessage('Failed to load pentest summary.');
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
      setMessageType('error');
      setMessage('Please confirm the reset phrase to proceed.');
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
        setMessageType('success');
        setMessage('Pentest progress reset successfully (open vulnerabilities preserved).');
        handleCloseResetDialog();
      }
    } catch (error) {
      setMessageType('error');
      setMessage(error.response?.data?.error || 'Failed to reset pentest progress.');
    } finally {
      setLoading(false);
    }
  };

  const getRoleChip = (role) => {
    const configs = {
      'admin': { label: 'Admin', color: theme.palette.error.main },
      'pentester': { label: 'Pentester', color: theme.palette.warning.main },
      'user': { label: 'User', color: theme.palette.primary.main }
    };
    const config = configs[role] || configs['user'];
    
    return (
      <Chip
        label={config.label}
        size="small"
        sx={{
          backgroundColor: alpha(config.color, 0.1),
          color: config.color,
          fontWeight: 500
        }}
      />
    );
  };

  const getSourceAvatar = (source) => {
    const colors = {
      'Production': '#f44336',
      'External': '#ff9800', 
      'Development': '#4caf50',
      'Testing': '#9c27b0',
      'Other': '#666666'
    };
    
    return (
      <Avatar
        sx={{
          width: 32,
          height: 32,
          fontSize: '0.875rem',
          backgroundColor: colors[source] || colors['Other'],
          mr: 1
        }}
      >
        {source?.charAt(0) || '?'}
      </Avatar>
    );
  };

  return (
    <Box sx={{ p: 3, backgroundColor: 'background.default', minHeight: '100vh' }}>
      {/* Alert */}
      <Box sx={{ position: 'fixed', top: 20, right: 20, zIndex: 9999 }}>
        {message && (
          <Alert 
            severity={messageType} 
            sx={{ minWidth: '400px', maxWidth: '400px' }}
            onClose={() => setMessage('')}
          >
            {message}
          </Alert>
        )}
      </Box>

      <Dialog open={resetDialogOpen} onClose={handleCloseResetDialog} maxWidth="sm" fullWidth>
        <DialogTitle>Confirm Pentest Progress Refresh</DialogTitle>
        <DialogContent>
          <Alert severity="warning" sx={{ mb: 2 }}>
            This action will delete all pentest progress except open vulnerabilities. This cannot be undone.
          </Alert>
          {resetSummary && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
                Current Summary
              </Typography>
              <Typography variant="body2">Total Targets: {resetSummary.total}</Typography>
              <Typography variant="body2">Completed Tests: {resetSummary.completed}</Typography>
              <Typography variant="body2">In Progress: {resetSummary.inProgress}</Typography>
              <Typography variant="body2">Not Started: {resetSummary.notStarted}</Typography>
              <Typography variant="body2">Vulnerable: {resetSummary.vulnerable}</Typography>
              <Typography variant="body2">Fixed/Closed: {resetSummary.fixed}</Typography>
              <Typography variant="body2">Open Vulnerabilities: {resetSummary.open}</Typography>
              <Typography variant="body2">Reports: {resetSummary.reports}</Typography>
              <Button
                variant="outlined"
                startIcon={<DownloadIcon />}
                onClick={downloadResetCsv}
                sx={{ mt: 1 }}
              >
                Download Summary CSV
              </Button>
            </Box>
          )}
          <Typography variant="body2" sx={{ mb: 2 }}>
            Type <strong>{requiredResetPhrase}</strong> to confirm.
          </Typography>
          <TextField
            fullWidth
            value={resetPhrase}
            onChange={(e) => setResetPhrase(e.target.value)}
            placeholder={requiredResetPhrase}
            sx={{ mb: 2 }}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={resetConfirmChecked}
                onChange={(e) => setResetConfirmChecked(e.target.checked)}
              />
            }
            label="I understand this will delete all pentest progress except open vulnerabilities."
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseResetDialog} disabled={loading}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="warning"
            onClick={handleResetOpenVulnerabilities}
            disabled={loading}
          >
            Reset Progress
          </Button>
        </DialogActions>
      </Dialog>

      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
        <Box>
          <Typography variant="h4" gutterBottom>
            System Administration
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Manage system settings, users, and infrastructure configuration
          </Typography>
        </Box>
        <Chip
          icon={<AdminIcon />}
          label="Admin Panel"
          sx={{
            backgroundColor: alpha(theme.palette.error.main, 0.1),
            color: theme.palette.error.main,
            fontWeight: 600
          }}
        />
      </Box>

      {/* Loading Indicator */}
      {loading && (
        <Box sx={{ mb: 3 }}>
          <LinearProgress />
        </Box>
      )}

      <Grid container spacing={3}>
        {/* System Actions */}
        <Grid item xs={12}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <RefreshIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  System Actions
                </Typography>
              </Box>
              <Button 
                variant="contained" 
                size="large"
                startIcon={<RefreshIcon />}
                onClick={handleManualParse}
                disabled={loading}
                sx={{
                  backgroundColor: theme.palette.secondary.main,
                  '&:hover': { backgroundColor: theme.palette.secondary.dark },
                  py: 1.5,
                  px: 3
                }}
              >
                Parse & Update Records
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                Manually trigger record parsing and database updates
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        {/* Reset Open Vulnerability Progress */}
        <Grid item xs={12}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                <WarningIcon sx={{ color: theme.palette.warning.main, mr: 1 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  Refresh Pentest Progress (Keep Open Vulns)
                </Typography>
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                Export current status and then delete all pentest progress except open vulnerabilities.
              </Typography>
              <Button
                variant="contained"
                color="warning"
                startIcon={<DeleteIcon />}
                onClick={handleOpenResetDialog}
                disabled={loading}
              >
                Review & Reset
              </Button>
              {resetStats && (
                <Box sx={{ mt: 2 }}>
                  <Alert severity="info">
                    Reset {resetStats.total_reset} record(s). Remaining open vulnerabilities: {resetStats.remaining_open}. Reports deleted: {resetStats.reports_deleted}, Report delete errors: {resetStats.report_delete_errors}.
                  </Alert>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* IP Source Management */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={3}>
                <StorageIcon sx={{ color: theme.palette.primary.main, mr: 1 }} />
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  IP Source Management
                </Typography>
              </Box>
              
              <Grid container spacing={3}>
                {/* Source Types */}
                <Grid item xs={12} md={4}>
                  <Paper sx={{ p: 2, backgroundColor: 'background.default', border: `1px solid ${theme.palette.divider}` }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2 }}>
                      Source Types
                    </Typography>
                    
                    <Box display="flex" gap={1} mb={2}>
                      <TextField 
                        placeholder="New Source Type" 
                        variant="outlined" 
                        size="small"
                        fullWidth 
                        value={newSourceName} 
                        onChange={(e) => setNewSourceName(e.target.value)}
                      />
                      <Button 
                        variant="contained" 
                        size="small"
                        startIcon={<AddIcon />}
                        onClick={handleAddSourceType}
                        disabled={loading}
                      >
                        Add
                      </Button>
                    </Box>
                    
                    {sourceTypes.length === 0 ? (
                      <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 2 }}>
                        No source types found
                      </Typography>
                    ) : (
                      <List sx={{ p: 0 }}>
                        {sourceTypes.map((srcName) => (
                          <ListItem 
                            key={srcName} 
                            button 
                            selected={selectedSource === srcName} 
                            onClick={() => handleSelectSourceType(srcName)}
                            sx={{
                              borderRadius: 1,
                              mb: 0.5,
                              '&.Mui-selected': {
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                '&:hover': {
                                  backgroundColor: alpha(theme.palette.primary.main, 0.15),
                                }
                              }
                            }}
                          >
                            {getSourceAvatar(srcName)}
                            <ListItemText 
                              primary={srcName}
                              secondary={`${(ipsBySource[srcName] || []).length} IPs`}
                            />
                          </ListItem>
                        ))}
                      </List>
                    )}
                  </Paper>
                </Grid>

                {/* IP Management */}
                <Grid item xs={12} md={8}>
                  <Paper sx={{ p: 2, backgroundColor: 'background.default', border: `1px solid ${theme.palette.divider}` }}>
                    {selectedSource === '' ? (
                      <Box sx={{ textAlign: 'center', py: 4 }}>
                        <ComputerIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                        <Typography variant="h6" color="text.secondary" gutterBottom>
                          Select a source type
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          Choose a source type from the left to view and manage its IP addresses
                        </Typography>
                      </Box>
                    ) : (
                      <>
                        <Box display="flex" alignItems="center" justifyContent="space-between" mb={2}>
                          <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                            IP Addresses for: {selectedSource}
                          </Typography>
                          <Chip 
                            label={`${(ipsBySource[selectedSource] || []).length} IPs`}
                            size="small"
                            sx={{
                              backgroundColor: alpha(theme.palette.info.main, 0.1),
                              color: theme.palette.info.main
                            }}
                          />
                        </Box>
                        
                        <Box display="flex" gap={1} mb={2}>
                          <TextField 
                            placeholder="New IP Address (e.g., 192.168.1.1)" 
                            variant="outlined" 
                            size="small"
                            fullWidth 
                            value={newIpAddress} 
                            onChange={(e) => setNewIpAddress(e.target.value)}
                            InputProps={{
                              startAdornment: (
                                <InputAdornment position="start">
                                  <ComputerIcon sx={{ fontSize: 20 }} />
                                </InputAdornment>
                              )
                            }}
                          />
                          <Button 
                            variant="contained" 
                            size="small"
                            startIcon={<AddIcon />}
                            onClick={handleAddIp}
                            disabled={loading}
                          >
                            Add IP
                          </Button>
                        </Box>
                        
                        <List sx={{ p: 0, maxHeight: 300, overflow: 'auto' }}>
                          {(ipsBySource[selectedSource] || []).map((ip) => (
                            <ListItem 
                              key={ip} 
                              sx={{ 
                                border: `1px solid ${theme.palette.divider}`,
                                borderRadius: 1,
                                mb: 1,
                                backgroundColor: 'background.paper',
                                '&:hover': { 
                                  backgroundColor: alpha(theme.palette.error.main, 0.05),
                                  borderColor: theme.palette.error.main
                                } 
                              }}
                            >
                              <ComputerIcon sx={{ mr: 1, color: 'text.secondary' }} />
                              <ListItemText 
                                primary={ip}
                                primaryTypographyProps={{ fontFamily: 'monospace', fontWeight: 500 }}
                              />
                              <Tooltip title="Delete IP">
                                <IconButton 
                                  edge="end" 
                                  color="error" 
                                  onClick={() => handleDeleteIpClick(ip)}
                                  size="small"
                                >
                                  <DeleteIcon />
                                </IconButton>
                              </Tooltip>
                            </ListItem>
                          ))}
                        </List>
                        
                        {(ipsToAdd.length > 0 || ipsToDelete.length > 0) && (
                          <Box mt={2}>
                            <Alert severity="info" sx={{ mb: 2 }}>
                              {ipsToAdd.length > 0 && `${ipsToAdd.length} IP(s) to add. `}
                              {ipsToDelete.length > 0 && `${ipsToDelete.length} IP(s) to delete.`}
                            </Alert>
                            <Button 
                              variant="contained" 
                              color="secondary" 
                              startIcon={<SaveIcon />}
                              onClick={handleSubmitChanges}
                              disabled={loading}
                              fullWidth
                            >
                              Submit Changes
                            </Button>
                          </Box>
                        )}
                      </>
                    )}
                  </Paper>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>

        {/* Security Settings */}
        <Grid item xs={12} md={6}>
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
        </Grid>

        {/* User Search & Add */}
        <Grid item xs={12} md={6}>
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
                {/* Available Users */}
                <Grid item xs={6}>
                  <Paper sx={{ p: 1, backgroundColor: 'background.default', height: 300, overflow: 'auto' }}>
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

                {/* Selected Users */}
                <Grid item xs={6}>
                  <Paper sx={{ p: 1, backgroundColor: 'background.default', height: 300, overflow: 'auto' }}>
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
        </Grid>

        {/* Local User Creation */}
        <Grid item xs={12} md={6}>
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
        </Grid>

        {/* Existing Users Management */}
        <Grid item xs={12}>
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
                    Add some users to get started
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
                              {user.email}
                            </Typography>
                          </Box>
                        </Box>
                        
                        <Box display="flex" alignItems="center" justifyContent="space-between">
                          <FormControl size="small" sx={{ minWidth: 100 }}>
                            <Select
                              value={editedUserRoles[user.username] || user.role}
                              onChange={(e) => {
                                const newRole = e.target.value;
                                setEditedUserRoles({...editedUserRoles, [user.username]: newRole});
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
                          {getRoleChip(editedUserRoles[user.username] || user.role)}
                        </Box>
                      </Paper>
                    </Grid>
                  ))}
                </Grid>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AdminSettings;
