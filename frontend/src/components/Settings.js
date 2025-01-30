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
} from '@mui/material';

const Settings = ({ darkMode }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [message, setMessage] = useState('');
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [messageType, setMessageType] = useState('');
  const [existingUsers, setExistingUsers] = useState([]);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [retypePassword, setRetypePassword] = useState('');

  /**
   * Handle selecting a user from the search results.
   * Moves the user to the selected users panel.
   */
  const handleSelectUser = (user) => {
    if (!selectedUsers.some((selected) => selected.username === user.username)) {
      setSelectedUsers([...selectedUsers, user]);
      setSearchResults(searchResults.filter((result) => result.username !== user.username));
    }
  };

  /**
   * Handle removing a user from the selected users panel.
   * Moves the user back to the search results panel.
   */
  const handleRemoveUser = (user) => {
    setSearchResults([...searchResults, user]);
    setSelectedUsers(selectedUsers.filter((selected) => selected.username !== user.username));
  };

  /**
   * Handle submitting all selected users to the backend.
   */
  const handleSubmit = async () => {
    selectedUsers.forEach(user => {
      handleAddUser(user.username, user.email);
    });
  };

  const handleAddUser = async (username, email) => {
    try {
      const response = await axios.post('/add-user', { username, email });
      if (response.status === 200) {
        setMessage(`User ${username} added successfully.`);
      }
    } catch (error) {
      console.error('Error adding user:', error);
      setMessage(`Failed to add user ${username}.`);
    } finally {
      setTimeout(() => setMessage(''), 2000);
    }
  };

  const handleSearch = async () => {
    try {
      setSearchResults([]);
      const response = await axios.get(`/ldap-search?query=${searchQuery}`);
      if (response.status === 200) {
        setSearchResults(response.data.results.filter(user => user.username != "None" && 
                          user.email != "None" && user.full_name != "None"));
      } else {
        setMessage('No results found.');
      }
    } catch (error) {
      console.error('Error searching LDAP:', error);
      setMessage('Error searching LDAP. Please try again.');
    } finally {
      setTimeout(() => setMessage(''), 2000);
    }
  };  

  useEffect(() => {
    const fetchExistingUsers = async () => {
      try {
        const response = await axios.get('/existing-users');
        if (response.status === 200) {
          setExistingUsers(response.data.users);
        }
      } catch (error) {
        console.error('Error fetching existing users:', error);
        setMessage('Failed to fetch existing users.');
      } finally {
        setTimeout(() => setMessage(''), 2000);
      }
    };
  
    fetchExistingUsers();
  }, []);

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
      console.error('Error changing password:', error);
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
              style={{ marginBottom: '1rem' }}
            />

            <TextField
              label="New Password"
              type="password"
              variant="outlined"
              fullWidth
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              style={{ marginBottom: '1rem' }}
            />

            <TextField
              label="Retype New Password"
              type="password"
              variant="outlined"
              fullWidth
              value={retypePassword}
              onChange={(e) => setRetypePassword(e.target.value)}
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
                    .filter((user) => !existingUsers.some((u) => u.username === user.username)) // Exclude users already in the system
                    .map((user) => (
                      <ListItem key={user.username} button onClick={() => handleSelectUser(user)}>
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
                    <ListItem key={user.username} button onClick={() => handleRemoveUser(user)}>
                      <ListItemText primary={`${user.full_name}`} secondary={`Email: ${user.email}`} />
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
                    <ListItemText primary={`${user.username}`} secondary={`Email: ${user.email}`} />
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

export default Settings;