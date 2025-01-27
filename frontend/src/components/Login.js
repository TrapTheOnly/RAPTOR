import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  TextField,
  Button,
  Typography,
  CssBaseline,
  Paper,
  ThemeProvider,
  createTheme,
} from '@mui/material';

const Login = ({ setLoggedIn, setGlobalUsername }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [darkMode, setDarkMode] = useState(localStorage.getItem('theme') === 'dark');
  let navigate = useNavigate();

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

  const handleLogin = async () => {
    try {
      const response = await axios.post(`/login`, {
        username,
        password,
      });
      if (response.status === 200) {
        setError('');
        setLoggedIn(true);
        setGlobalUsername(response.data.username);
        navigate('/');
      }
    } catch (error) {
      setError('Invalid credentials. Please try again.');
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
        bgcolor={darkMode ? '#121212' : '#f5f5f5'}
      >
        <Paper
          elevation={3}
          style={{
            padding: '2rem',
            maxWidth: '400px',
            width: '100%',
            textAlign: 'center',
          }}
        >
          <Typography variant="h4" component="h1" gutterBottom>
            Login
          </Typography>
          {error && (
            <Typography variant="body1" color="error" gutterBottom>
              {error}
            </Typography>
          )}
          <Box mb={2}>
            <TextField
              fullWidth
              label="Username"
              variant="outlined"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              margin="normal"
            />
            <TextField
              fullWidth
              type="password"
              label="Password"
              variant="outlined"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              margin="normal"
            />
          </Box>
          <Button
            variant="contained"
            color="primary"
            fullWidth
            onClick={handleLogin}
            type="submit"
          >
            Login
          </Button>
          <Typography
            variant="body2"
            style={{ marginTop: '1rem', cursor: 'pointer' }}
            onClick={() => setDarkMode(!darkMode)}
          >
            {darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          </Typography>
        </Paper>
      </Box>
    </ThemeProvider>
  );
};

export default Login;