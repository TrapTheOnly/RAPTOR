import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  TextField, 
  Button, 
  Box, 
  Typography, 
  Paper, 
  List, 
  ListItem,
  ListItemText,
  ThemeProvider,
  createTheme,
  CssBaseline,
  IconButton
} from '@mui/material';
import DeleteIcon from '@mui/icons-material/Delete';

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
  const [editedUserRoles, setEditedUserRoles] = useState({}); //Store edited roles 

  /*************************************************************************
   * 1) FETCH & PARSE IP SOURCES ON LOAD
   *************************************************************************/
  useEffect(() => {
    fetchIpSources();
    fetchExistingUsers(); 
  }, []);

  const fetchIpSources = async () => {
    try {
      const response = await axios.get('/ip-sources');
      if (response.status === 200 && response.data.ip_sources) {
        const ipSourcesArray = response.data.ip_sources; 

        // Build a set of distinct source_name
        const sourceSet = new Set();
        // Build a map from source_name => array of ips
        const map = {};

        ipSourcesArray.forEach(item => {
          const src = item.source_name;
          sourceSet.add(src);
          if (!map[src]) {
            map[src] = [];
          }
          map[src].push(item.ip_address);
        });
        setSourceTypes(Array.from(sourceSet));
        setIpsBySource(map);
      }
    } catch (error) {
      setMessageType('error');
      setMessage('Failed to fetch IP sources.');
      console.error(error);
    }
  };

  /*************************************************************************
   * 2) ADD NEW SOURCE TYPE (locally, no IP assigned yet)
   *************************************************************************/
  const handleAddSourceType = () => {
    const trimmedName = newSourceName.trim();
    if (!trimmedName) return;
    
    // If the type already exists, skip
    if (sourceTypes.includes(trimmedName)) {
      setMessageType('error');
      setMessage('This source type already exists.');
      setTimeout(() => setMessage(''), 2000);
      return;
    }

    // Add to local state
    setSourceTypes([...sourceTypes, trimmedName]);
    setIpsBySource({ ...ipsBySource, [trimmedName]: [] });
    setSelectedSource(trimmedName);
    setNewSourceName('');
  };

  /*************************************************************************
   * 3) SELECT A SOURCE TYPE
   *************************************************************************/
  const handleSelectSourceType = (srcName) => {
    setSelectedSource(srcName);
    setIpsToAdd([]);     // reset staged additions
    setIpsToDelete([]);  // reset staged deletions
    setNewIpAddress(''); // clear IP field
  };

  /*************************************************************************
   * 4) STAGE A NEW IP ADDRESS FOR ADDITION
   *************************************************************************/
  const handleAddIp = () => {
    const trimmedIp = newIpAddress.trim();
    if (!trimmedIp || !selectedSource) return;

    // Check if it already exists in local state
    const currentIps = ipsBySource[selectedSource] || [];
    if (currentIps.includes(trimmedIp)) {
      setMessageType('error');
      setMessage('IP already exists in this source.');
      setTimeout(() => setMessage(''), 2000);
      return;
    }

    // Add it locally
    const updatedIps = [...currentIps, trimmedIp];
    setIpsBySource({ ...ipsBySource, [selectedSource]: updatedIps });

    // Stage it for addition
    setIpsToAdd([...ipsToAdd, trimmedIp]);
    setNewIpAddress('');
  };

  /*************************************************************************
   * 5) STAGE AN IP ADDRESS FOR DELETION
   *************************************************************************/
  const handleDeleteIpClick = (ip) => {
    // Mark the IP for deletion if it's an existing IP
    if (!ipsToDelete.includes(ip)) {
      setIpsToDelete([...ipsToDelete, ip]);
    }
    // Also remove it from local display
    const updatedIps = (ipsBySource[selectedSource] || []).filter(x => x !== ip);
    setIpsBySource({ ...ipsBySource, [selectedSource]: updatedIps });
  };

  /*************************************************************************
   * 6) SUBMIT CHANGES (Add + Delete) ONE-BY-ONE
   *************************************************************************/
  const handleSubmitChanges = async () => {
    if (!selectedSource) return;

    // 1) Add the new IPs
    for (const ip of ipsToAdd) {
      try {
        await axios.post('/ip-sources', {
          source_name: selectedSource,
          ip_address: ip
        });
      } catch (error) {
        console.error(`Failed to add IP: ${ip}`, error);
      }
    }

    // 2) Delete the staged IPs
    for (const ip of ipsToDelete) {
      try {
        await axios.delete('/ip-sources', {
          data: { ip_address: ip }
        });
      } catch (error) {
        console.error(`Failed to delete IP: ${ip}`, error);
      }
    }

    setMessageType('success');
    setMessage('Changes submitted successfully.');
    setTimeout(() => setMessage(''), 2000);

    // Clear staging
    setIpsToAdd([]);
    setIpsToDelete([]);

    // Refresh from server to ensure we’re in sync
    fetchIpSources();
  };

  /**
   * Handle selecting a user from the search results.
   * Moves the user to the selected users panel.
   */
  const handleSelectUser = (user) => {
    if (!selectedUsers.some((selected) => selected.username === user.username)) {
      setSelectedUsers([...selectedUsers, user]);
      setSearchResults(searchResults.filter((result) => result.username !== user.username));
      setSelectedUserRoles({ ...selectedUserRoles, [user.username]: 'user' });
    }
  };

  /**
   * Handle removing a user from the selected users panel.
   * Moves the user back to the search results panel.
   */
  const handleRemoveUser = (user) => {
    setSearchResults([...searchResults, user]);
    setSelectedUsers(selectedUsers.filter((selected) => selected.username !== user.username));
    const { [user.username]: removedRole, ...restRoles } = selectedUserRoles;
    setSelectedUserRoles(restRoles);
  };

  /**
   * Handle submitting all selected users to the backend.
   */
  const handleSubmit = async () => {
    try {
      // Map selected users to include their selected roles.
      const usersWithRoles = selectedUsers.map(user => ({
        username: user.username,
        email: user.email,
        role: selectedUserRoles[user.username] || 'user', // Get the role, default to 'user'
      }));
  
      const responses = await Promise.all(
        usersWithRoles.map(user => axios.post('/add-user', user)) // Send user object directly
      );
  
      // Check if all requests were successful
      if (responses.every(response => response.status === 200)) {
        setMessageType('success');
        setMessage('Users added successfully.');
        setSelectedUsers([]);
        setSelectedUserRoles({}); // Clear roles after successful submission
  
        setTimeout(() => {
          window.location.reload();
        }, 1000);
      }
    } catch (error) {
      setMessageType('error');
      setMessage('Failed to add users. Please try again.');
    } finally {
      setTimeout(() => setMessage(''), 2000);
    }
  };

  const handleSaveRole = async (username, newRole) => {
    try {
      const response = await axios.post('/update-user-role', {
        username: username,
        role: newRole
      });
        if (response.status === 200) {
          //Update the role, to reflect changes without reloading
            setExistingUsers(prevUsers => {
                const updatedUsers = prevUsers.map(user => {
                  if (user.username === username) {
                    return { ...user, role: newRole }; // Update the role
                  }
                  return user;
                });
                return updatedUsers;
            });
            setMessageType('success');
            setMessage(response.data.message);

        } else {
            setMessageType('error');
            setMessage('Failed to update role. Please try again.');
        }

    } catch (error) {
        setMessageType('error');
        setMessage(
          error.response?.data?.error || 'Failed to update user role.  Please try again.'
        );
    } finally {
      setTimeout(() => setMessage(''), 2000);
    }
  };

  /**
   * Handle deleting a user from the system.
   */
  const handleDeleteUser = async (username) => {
    try {
      const response = await axios.delete(`/delete-user`, { data: { username } });
      if (response.status === 200) {
        setMessageType('success');
        setMessage(`User ${username} deleted successfully.`);
        setExistingUsers(existingUsers.filter((user) => user.username !== username));
      }
    } catch (error) {
      setMessageType('error');
      setMessage(`Failed to delete user ${username}.`);
    } finally {
      setTimeout(() => setMessage(''), 2000);
    }
  };

  /**
   * Manually trigger zone file parsing.
   */
  const handleManualParse = async () => {
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
      // Clear the message after a short delay
      setTimeout(() => setMessage(''), 2000);
    }
  };

  /**
   * Handle searching a user in LDAP.
   */
  const handleSearch = async () => {
    try {
      setSearchResults([]);
      const response = await axios.get(`/ldap-search?query=${searchQuery}`);
      if (response.status === 200) {
        setSearchResults(response.data.results.filter(user => user.username != "None" && 
                          user.email != "None" && user.full_name != "None"));
      } else {
        setMessageType('error');
        setMessage('No results found.');
      }
    } catch (error) {
      setMessageType('error');
      setMessage('Error searching LDAP. Please try again.');
    } finally {
      setTimeout(() => setMessage(''), 2000);
    }
  };  

  // Handle Enter key for search form
  const handleSearchKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
      e.preventDefault();
    }
  };

  // Handle Enter key for password change form
  const handlePasswordKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleChangePassword();
      e.preventDefault();
    }
  };

  const fetchExistingUsers = async () => {
    try {
      const response = await axios.get('/existing-users');
      if (response.status === 200) {
        setExistingUsers(response.data.users);
      }
    } catch (error) {
      setMessageType('error');
      setMessage('Failed to fetch existing users.');
    } finally {
      setTimeout(() => setMessage(''), 2000);
    }
  };


  const handleChangePassword = async () => {
    if (newPassword !== retypePassword) {
      setMessageType('error');
      setMessage('New password and retyped password do not match.');
      setTimeout(() => setMessage(''), 2000);
      return;
    }

    try {
      const response = await axios.post('/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
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
      setTimeout(() => setMessage(''), 2000);
    }
  };

  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: darkMode ? '#90caf9' : '#1976d2',
      },
      secondary: {
        main: darkMode ? '#f48fb1' : '#d81b60',
      },
    },
  });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
        padding="2rem"
        bgcolor={theme.palette.background.default}
      >
        <Paper elevation={3} style={{ padding: '2rem', width: '900px', maxWidth: '95%' }}>
          <Typography variant="h4" align="center" gutterBottom>
            Admin Settings
          </Typography>
  
          {/* Notifications */}
          {message && (
            <Typography
              variant="body1"
              align="center"
              style={{
                color: messageType === 'success' ? 'green' : 'red',
                marginBottom: '1rem',
              }}
            >
              {message}
            </Typography>
          )}

          <Box mb={3}>
            <Button variant="contained" color="secondary" fullWidth onClick={handleManualParse}>
              Parse Records
            </Button>
          </Box>

          {/* IP Source Management Section */}
          <Typography variant="h6" gutterBottom>
              IP Source Management
            </Typography>
          <Box display="flex" gap="2rem" mb={4}>
            {/* Left Pane: List of Source Types */}
            <Box flex={1} border="1px solid" borderColor={theme.palette.divider} p={2}>
              <Typography variant="h6" gutterBottom>Source Types</Typography>

              {/* Input to Add a New Source Type */}
              <TextField
                label="New Source Type"
                variant="outlined"
                fullWidth
                value={newSourceName}
                onChange={(e) => setNewSourceName(e.target.value)}
                style={{ marginBottom: '1rem' }}
              />
              <Button 
                variant="contained" 
                color="primary" 
                fullWidth 
                onClick={handleAddSourceType}
                style={{ marginBottom: '1rem' }}
              >
                Add Type
              </Button>

              {/* Existing Types List */}
              {sourceTypes.length === 0 ? (
                <Typography variant="body2" color="textSecondary">
                  No source types found.
                </Typography>
              ) : (
                <List>
                  {sourceTypes.map((srcName) => (
                    <ListItem 
                      key={srcName} 
                      style={{ cursor: 'pointer' }}
                      button 
                      selected={selectedSource === srcName}
                      onClick={() => handleSelectSourceType(srcName)}
                    >
                      <ListItemText primary={srcName} />
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>

            {/* Right Pane: IP Addresses for Selected Type */}
            <Box flex={2} border="1px solid" borderColor={theme.palette.divider} p={2}>
              {selectedSource === '' ? (
                <Typography variant="body1">
                  Select a source type on the left to view and manage its IP addresses.
                </Typography>
              ) : (
                <>
                  <Typography variant="h6" gutterBottom>
                    IPs for: {selectedSource}
                  </Typography>

                  {/* Input to Add a New IP */}
                  <Box display="flex" mb={2}>
                    <TextField
                      label="New IP Address"
                      variant="outlined"
                      fullWidth
                      value={newIpAddress}
                      onChange={(e) => setNewIpAddress(e.target.value)}
                      style={{ marginRight: '1rem' }}
                    />
                    <Button 
                      variant="contained" 
                      color="primary" 
                      onClick={handleAddIp}
                    >
                      Add IP
                    </Button>
                  </Box>

                  {/* List of IPs */}
                  <List>
                    {(ipsBySource[selectedSource] || []).map((ip) => (
                      <ListItem key={ip} sx={{
                        cursor: 'pointer',
                        '&:hover': {
                          backgroundColor: 'action.hover',
                        },
                      }} secondaryAction={
                        <IconButton edge="end" color="error" onClick={() => handleDeleteIpClick(ip)}>
                          <DeleteIcon />
                        </IconButton>
                      }>
                        <ListItemText primary={ip} />
                      </ListItem>
                    ))}
                  </List>

                  {/* If we have something to add or delete, show a "Submit Changes" button */}
                  {(ipsToAdd.length > 0 || ipsToDelete.length > 0) && (
                    <Box mt={2}>
                      <Button
                        variant="contained"
                        color="secondary"
                        fullWidth
                        onClick={handleSubmitChanges}
                      >
                        Submit Changes
                      </Button>
                    </Box>
                  )}
                </>
              )}
            </Box>
          </Box>
  
          {/* Change Password Section */}
          <Box mb={3}>
            <Typography variant="h6" gutterBottom>
              Change Admin Password
            </Typography>

            <TextField
              label="Current Password"
              type="password"
              variant="outlined"
              fullWidth
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              onKeyDown={handlePasswordKeyDown}
              style={{ marginBottom: '1rem' }}
            />

            <TextField
              label="New Password"
              type="password"
              variant="outlined"
              fullWidth
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              onKeyDown={handlePasswordKeyDown}
              style={{ marginBottom: '1rem' }}
            />

            <TextField
              label="Retype New Password"
              type="password"
              variant="outlined"
              fullWidth
              value={retypePassword}
              onChange={(e) => setRetypePassword(e.target.value)}
              onKeyDown={handlePasswordKeyDown}
              style={{ marginBottom: '1rem' }}
            />

            <Button variant="contained" color="primary" fullWidth onClick={handleChangePassword}>
              Change Password
            </Button>
          </Box>
  
          {/* Search and User Management */}
          <Typography variant="h6" gutterBottom>
              Add Domain Users
            </Typography>
          <Box display="flex" justifyContent="space-between" mb={2}>
            <TextField
              label="Search Domain User"
              variant="outlined"
              fullWidth
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={handleSearchKeyDown}
              style={{ flex: 1, marginRight: '1rem' }}
            />
            <Button variant="contained" color="primary" onClick={handleSearch}>
              Search
            </Button>
          </Box>
  
          <Box display="flex" flexDirection="row" justifyContent="space-between" height="400px">
            {/* Available Users Panel */}
            <Box flex={1} padding="1rem" overflow="auto" border="1px solid" borderColor={theme.palette.divider}>
              <Typography variant="h6" gutterBottom>
                Available Users
              </Typography>
              {searchResults.length === 0 ? (
                <Typography variant="body2" color="textSecondary">
                  No users found.
                </Typography>
              ) : (
                <List>
                  {searchResults
                    .filter((user) => !existingUsers.some((u) => u.username === user.username))
                    .map((user) => (
                      <ListItem key={user.username} button onClick={() => handleSelectUser(user)} style={{ cursor: 'pointer' }}>
                        <ListItemText primary={`${user.full_name}`} secondary={`Email: ${user.email}`} />
                      </ListItem>
                    ))}
                </List>
              )}
            </Box>
  
            {/* Selected Users Panel */}
            <Box flex={1} padding="1rem" marginLeft="1rem" overflow="auto" border="1px solid" borderColor={theme.palette.divider}>
                <Typography variant="h6" gutterBottom>
                    Selected Users
                </Typography>
                {selectedUsers.length === 0 ? (
                    <Typography variant="body2" color="textSecondary">
                        No users selected. Click a user to add them here.
                    </Typography>
                ) : (
                    <List>
                        {selectedUsers.map((user) => (
                            <ListItem key={user.username}>
                                <ListItemText primary={`${user.full_name}`} secondary={`Email: ${user.email}`} />
                                <select
                                    value={selectedUserRoles[user.username] || 'user'} // Get role, default to 'user'
                                    onChange={(e) => {
                                        const newRole = e.target.value;
                                        setSelectedUserRoles({
                                          ...selectedUserRoles,
                                          [user.username]: newRole,
                                        }); // Update local state
                                      }}
                                    style={{marginRight: "10px"}}
                                >
                                    <option value="user">User</option>
                                    <option value="pentester">Pentester</option>
                                    {/* No 'admin' option */}
                                </select>
                                <IconButton edge="end" color="error" onClick={() => handleRemoveUser(user)}>
                                    <DeleteIcon />
                                </IconButton>
                            </ListItem>
                        ))}
                    </List>
                )}
                {selectedUsers.length > 0 && (
                    <Button variant="contained" color="secondary" fullWidth onClick={handleSubmit}>
                        Submit Users
                    </Button>
                )}
            </Box>
          </Box>
  
          {/* Existing Users Panel */}
          <Box mt={3}>
            <Typography variant="h6" gutterBottom>
              Existing Users in the System
            </Typography>
            {existingUsers.length === 0 ? (
              <Typography variant="body2" color="textSecondary">
                No users found in the system.
              </Typography>
            ) : (
              <List>
                {existingUsers.map((user) => (
                  <ListItem key={user.username}>
                    <ListItemText
                      primary={user.username}
                      secondary={`Email: ${user.email}`}
                    />
                    <select
                      value={editedUserRoles[user.username] || user.role}
                      onChange={(e) => {
                          const newRole = e.target.value;
                          setEditedUserRoles({...editedUserRoles, [user.username]: newRole});
                          handleSaveRole(user.username, newRole);
                      }}
                      style={{marginRight: '10px'}}
                    >
                      <option value="user">User</option>
                      <option value="pentester">Pentester</option>
                    </select>
                    <IconButton edge="end" color="error" onClick={() => handleDeleteUser(user.username)}>
                      <DeleteIcon />
                    </IconButton>
                  </ListItem>
                ))}
              </List>
            )}
          </Box>
        </Paper>
      </Box>
    </ThemeProvider>
  );
};

export default AdminSettings;