import axios from 'axios';
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Alert,
  IconButton,
  InputAdornment,
  useTheme
} from '@mui/material';
import {
  Visibility,
  VisibilityOff,
  LoginOutlined
} from '@mui/icons-material';
import { useState, useEffect } from 'react';

const ModernLogin = ({ setLoggedIn, setGlobalUsername, setGlobalUserRole, darkMode = false }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const theme = useTheme();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await axios.post('/login', {
        username: username,
        password: password,
      });

      if (response.status === 200) {
        setLoggedIn(true);
        setGlobalUsername(username);
        setGlobalUserRole(response.data.user_type);
      }
    } catch (error) {
      if (error.response?.status === 401) {
        setError('Invalid username or password');
      } else {
        setError('Login failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  return (
      <Box
        sx={{
          minHeight: '100vh',
          backgroundColor: 'background.default',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          p: 2,
        }}
      >
        <Paper
          elevation={0}
          sx={{
            p: 4,
            width: '100%',
            maxWidth: 400,
            textAlign: 'center',
          backgroundColor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          boxShadow: darkMode ? 'none' : '0 4px 8px rgba(0,0,0,0.1)',
          }}
        >
          {/* Logo/Brand */}
          <Box mb={4}>
            <Typography 
              variant="h4" 
              gutterBottom
              sx={{ 
                fontWeight: 300,
                letterSpacing: '-0.02em',
              color: 'text.primary'
              }}
            >
              DNS<span style={{ fontWeight: 600 }}>Radar</span>
            </Typography>
            <Typography variant="body2" color="text.secondary">
              DNS Monitoring & Security Assessment Platform
            </Typography>
          </Box>

          {/* Login Form */}
          <Box component="form" onSubmit={handleSubmit} sx={{ mt: 3 }}>
            {error && (
              <Alert 
                severity="error" 
                sx={{ 
                  mb: 3,
                backgroundColor: darkMode ? '#2d1b1b' : '#ffeaa7',
                color: darkMode ? '#ffffff' : '#d63031',
                  border: '1px solid #f44336',
                  '& .MuiAlert-icon': {
                    color: '#f44336',
                  },
                }}
              >
                {error}
              </Alert>
            )}

            <TextField
              fullWidth
              label="Username"
              variant="outlined"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              autoFocus
            sx={{ 
              mb: 3,
              '& .MuiOutlinedInput-root': {
                backgroundColor: darkMode ? 'rgba(255,255,255,0.05)' : 'background.paper',
                '& fieldset': {
                  borderColor: theme.palette.divider,
                },
                '&:hover fieldset': {
                  borderColor: theme.palette.primary.main,
                },
                '&.Mui-focused fieldset': {
                  borderColor: theme.palette.primary.main,
                },
              },
            }}
            />

            <TextField
              fullWidth
              label="Password"
              type={showPassword ? 'text' : 'password'}
              variant="outlined"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            sx={{ 
              mb: 4,
              '& .MuiOutlinedInput-root': {
                backgroundColor: darkMode ? 'rgba(255,255,255,0.05)' : 'background.paper',
                '& fieldset': {
                  borderColor: theme.palette.divider,
                },
                '&:hover fieldset': {
                  borderColor: theme.palette.primary.main,
                },
                '&.Mui-focused fieldset': {
                  borderColor: theme.palette.primary.main,
                },
              },
            }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={handleTogglePasswordVisibility}
                      edge="end"
                    sx={{ color: 'text.secondary' }}
                    >
                      {showPassword ? <VisibilityOff /> : <Visibility />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              disabled={loading || !username || !password}
              startIcon={<LoginOutlined />}
              sx={{ mb: 2 }}
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </Button>
          </Box>

          {/* Footer */}
          <Box mt={4}>
            <Typography variant="caption" color="text.secondary">
              Secure authentication via LDAP
            </Typography>
          </Box>
        </Paper>
      </Box>
  );
};

export default ModernLogin;