import React, { useState } from 'react';
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
    }
  };

  const handleAddUser = async (username) => {
    try {
      const response = await axios.post('/add-user', { username });
      if (response.status === 200) {
        setMessage(`User ${username} added successfully.`);
      }
    } catch (error) {
      console.error('Error adding user:', error);
      setMessage(`Failed to add user ${username}.`);
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
        <Paper elevation={3} style={{ padding: '2rem', width: '700px', maxWidth: '90%' }}>
          <Typography variant="h4" align="center" gutterBottom>
            Admin Settings
          </Typography>
          
          {/* Search Section */}
          <Box display="flex" justifyContent="space-between" flexWrap="wrap" mb={2}>
            <TextField
              label="Search Domain User"
              variant="outlined"
              fullWidth
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{ flex: 1, marginBottom: '1rem' }}
            />
            <Button
              variant="contained"
              color="primary"
              onClick={handleSearch}
              style={{ marginLeft: '1rem', height: '56px' }}
            >
              Search
            </Button>
          </Box>
  
          {/* Display search messages */}
          {message && (
            <Typography variant="body1" color="error" align="center" style={{ marginBottom: '1rem' }}>
              {message}
            </Typography>
          )}
  
          {/* Results Section */}
          <Box
            display="flex"
            flexDirection="row"
            justifyContent="space-between"
            height="400px"
            overflow="hidden"
          >
            {/* Search Results */}
            <Box flex={1} padding="1rem" overflow="auto" border="1px solid" borderColor={theme.palette.divider}>
              <Typography variant="h6" gutterBottom>
                Search Results
              </Typography>
              {searchResults.length === 0 ? (
                <Typography variant="body2" color="textSecondary">
                  No results found. Try a different search term.
                </Typography>
              ) : (
                <List>
                  {searchResults.map((user) => (
                    <ListItem key={user.username} button onClick={() => handleAddUser(user.username)}>
                      <ListItemText
                        primary={`${user.full_name}`}
                        secondary={`Email: ${user.email}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )}
            </Box>
  
            {/* Actions or Information Panel */}
            <Box flex={1} padding="1rem" marginLeft="1rem" overflow="auto" bgcolor={theme.palette.background.paper}>
              <Typography variant="h6" gutterBottom>
                Instructions / Actions
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Select a user from the search results to add them to the system. Ensure the user has a valid username and email address.
              </Typography>
              <Typography variant="body2" style={{ marginTop: '1rem' }}>
                <strong>Note:</strong> Only users with both valid usernames and email addresses will be displayed.
              </Typography>
            </Box>
          </Box>
        </Paper>
      </Box>
    </ThemeProvider>
  );
};

export default Settings;