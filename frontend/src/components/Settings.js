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
} from '@mui/material';

const Settings = ({ darkMode }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [message, setMessage] = useState('');

  const handleSearch = async () => {
    try {
      const response = await axios.get(`/ldap-search?query=${searchQuery}`);
      if (response.status === 200) {
        setSearchResults(response.data.results);
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
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
      <Paper elevation={3} style={{ padding: '2rem', width: '500px' }}>
        <Typography variant="h5" gutterBottom>
          Admin Settings
        </Typography>
        <TextField
          label="Search Domain User"
          variant="outlined"
          fullWidth
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ marginBottom: '1rem' }}
        />
        <Button variant="contained" color="primary" fullWidth onClick={handleSearch}>
          Search
        </Button>
        {message && <Typography color="error" style={{ marginTop: '1rem' }}>{message}</Typography>}
        <List>
          {searchResults.map((user) => (
            <ListItem key={user.username} button onClick={() => handleAddUser(user.username)}>
              <ListItemText primary={`${user.username} (${user.email})`} />
            </ListItem>
          ))}
        </List>
      </Paper>
      </Box>
    </ThemeProvider>
  );
};

export default Settings;