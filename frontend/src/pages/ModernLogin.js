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

const MIN_PASSWORD_LENGTH = 12;
const MAX_PASSWORD_LENGTH = 64;
const COMMON_PASSWORDS = new Set([
  'password', 'password1', '123456', '12345678', '123456789',
  'qwerty', 'qwerty123', 'letmein', 'welcome', 'admin',
  'admin123', 'iloveyou', 'monkey', 'dragon', 'football',
  'abc123', '111111', 'trustno1', 'sunshine', 'princess',
  'login', 'qwertyuiop', 'passw0rd', 'master', 'shadow'
]);

const ModernLogin = ({
  setLoggedIn,
  setGlobalUsername,
  setGlobalUserRole,
  setGlobalUserPermissions,
  setPasswordResetRequired,
  passwordResetRequired = false,
  resetUsername = '',
  resetUserType = null,
  setResetUserType = () => {},
  darkMode = false
}) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [resetError, setResetError] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const theme = useTheme();

  useEffect(() => {
    setResetMode(passwordResetRequired);
  }, [passwordResetRequired]);

  useEffect(() => {
    if (resetMode && resetUsername) {
      setUsername(resetUsername);
    }
  }, [resetMode, resetUsername]);

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
        if (response.data.status === 'password_reset_required') {
          setResetMode(true);
          setPasswordResetRequired(true);
          setResetUserType(response.data.user_type || null);
          setError('');
        } else if (response.data.status === 'logged_in') {
          setLoggedIn(true);
          setPasswordResetRequired(false);
          setResetUserType(null);
          setGlobalUsername(username);
          setGlobalUserRole(response.data.user_type);
          setGlobalUserPermissions(response.data.permissions || []);
        }
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

  const validatePassword = (value) => {
    if (!value) return 'Password is required.';
    if (value.length < MIN_PASSWORD_LENGTH) {
      return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
    }
    if (value.length > MAX_PASSWORD_LENGTH) {
      return `Password must be at most ${MAX_PASSWORD_LENGTH} characters.`;
    }
    if (COMMON_PASSWORDS.has(value.trim().toLowerCase())) {
      return 'Password is too common.';
    }
    if (username && value.toLowerCase().includes(username.toLowerCase())) {
      return 'Password must not contain the username.';
    }
    return '';
  };

  const handleResetSubmit = async (e) => {
    e.preventDefault();
    setResetError('');
    const validationError = validatePassword(newPassword);
    if (validationError) {
      setResetError(validationError);
      return;
    }
    if (newPassword !== confirmPassword) {
      setResetError('Passwords do not match.');
      return;
    }

    setResetLoading(true);
    try {
      const endpoint = resetUserType === 'admin' ? '/admin-reset-password' : '/user-reset-password';
      const response = await axios.post(endpoint, {
        new_password: newPassword
      });
      if (response.status === 200 && response.data.status === 'logged_in') {
        setLoggedIn(true);
        setPasswordResetRequired(false);
        setResetUserType(null);
        setGlobalUsername(response.data.username || username);
        setGlobalUserRole(response.data.user_type || 'user');
        setGlobalUserPermissions(response.data.permissions || []);
      }
    } catch (error) {
      setResetError(error.response?.data?.error || 'Password reset failed. Please try again.');
    } finally {
      setResetLoading(false);
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
              variant="h3" 
              sx={{ 
                fontWeight: 700,
                fontSize: '2.5rem',
                letterSpacing: '0.15em',
                background: theme.palette.mode === 'dark'
                  ? 'linear-gradient(45deg, #00d4ff 30%, #1976d2 90%)'
                  : 'linear-gradient(45deg, #1976d2 30%, #0d47a1 90%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
                mb: 1,
                textAlign: 'center',
                position: 'relative',
                display: 'inline-block',
                transform: 'translateZ(0)',
                animation: 'raptorLoginGlow 8s ease-in-out infinite alternate, raptorLoginFloat 12s ease-in-out infinite',
                transition: 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
                '&::before': {
                  content: '"RAPTOR"',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  background: theme.palette.mode === 'dark'
                    ? 'linear-gradient(45deg, rgba(255, 64, 129, 0.2) 30%, rgba(233, 30, 99, 0.2) 90%)'
                    : 'linear-gradient(45deg, rgba(25, 118, 210, 0.15) 30%, rgba(13, 71, 161, 0.15) 90%)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  color: 'transparent',
                  opacity: 0,
                  transform: 'translate(2px, 2px)',
                  animation: 'raptorLoginShimmer1 10s ease-in-out infinite',
                  zIndex: -1,
                  filter: 'blur(0.3px)',
                },
                '&::after': {
                  content: '"RAPTOR"',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  background: theme.palette.mode === 'dark'
                    ? 'linear-gradient(45deg, rgba(0, 255, 136, 0.15) 30%, rgba(76, 175, 80, 0.15) 90%)'
                    : 'linear-gradient(45deg, rgba(25, 118, 210, 0.1) 30%, rgba(13, 71, 161, 0.1) 90%)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  color: 'transparent',
                  opacity: 0,
                  transform: 'translate(-2px, -2px)',
                  animation: 'raptorLoginShimmer2 10s ease-in-out infinite 2s',
                  zIndex: -2,
                  filter: 'blur(0.3px)',
                },
                '&:hover': {
                  transform: 'translateY(-2px) scale(1.05) translateZ(0)',
                  filter: theme.palette.mode === 'dark'
                    ? 'drop-shadow(0 8px 25px rgba(0, 212, 255, 0.2))'
                    : 'drop-shadow(0 8px 25px rgba(25, 118, 210, 0.2))',
                  animation: 'raptorLoginGlow 4s ease-in-out infinite alternate, raptorLoginFloat 6s ease-in-out infinite',
                  '&::before': {
                    opacity: 0.4,
                    animation: 'raptorLoginHoverShimmer1 3s ease-in-out infinite',
                  },
                  '&::after': {
                    opacity: 0.3,
                    animation: 'raptorLoginHoverShimmer2 3s ease-in-out infinite 0.5s',
                  }
                },
                '@keyframes raptorLoginGlow': {
                  '0%': {
                    textShadow: theme.palette.mode === 'dark'
                      ? '0 0 10px rgba(0, 212, 255, 0.4), 0 0 20px rgba(25, 118, 210, 0.2)'
                      : '0 0 10px rgba(25, 118, 210, 0.3), 0 0 20px rgba(13, 71, 161, 0.15)',
                    filter: 'brightness(1) saturate(1)',
                  },
                  '50%': {
                    textShadow: theme.palette.mode === 'dark'
                      ? '0 0 15px rgba(0, 212, 255, 0.6), 0 0 30px rgba(25, 118, 210, 0.3), 0 0 45px rgba(25, 118, 210, 0.1)'
                      : '0 0 15px rgba(25, 118, 210, 0.5), 0 0 30px rgba(13, 71, 161, 0.25), 0 0 45px rgba(13, 71, 161, 0.1)',
                    filter: 'brightness(1.15) saturate(1.1)',
                  },
                  '100%': {
                    textShadow: theme.palette.mode === 'dark'
                      ? '0 0 10px rgba(0, 212, 255, 0.4), 0 0 20px rgba(25, 118, 210, 0.2)'
                      : '0 0 10px rgba(25, 118, 210, 0.3), 0 0 20px rgba(13, 71, 161, 0.15)',
                    filter: 'brightness(1) saturate(1)',
                  }
                },
                '@keyframes raptorLoginFloat': {
                  '0%, 100%': {
                    transform: 'translateY(0px) translateZ(0)',
                  },
                  '25%': {
                    transform: 'translateY(-2px) translateZ(0)',
                  },
                  '50%': {
                    transform: 'translateY(-4px) translateZ(0)',
                  },
                  '75%': {
                    transform: 'translateY(-2px) translateZ(0)',
                  }
                },
                '@keyframes raptorLoginShimmer1': {
                  '0%, 85%, 100%': {
                    opacity: 0,
                    transform: 'translate(2px, 2px)',
                  },
                  '5%, 8%': {
                    opacity: 0.2,
                    transform: 'translate(-1px, 1px)',
                  },
                  '40%, 43%': {
                    opacity: 0.15,
                    transform: 'translate(1px, -1px)',
                  }
                },
                '@keyframes raptorLoginShimmer2': {
                  '0%, 90%, 100%': {
                    opacity: 0,
                    transform: 'translate(-2px, -2px)',
                  },
                  '7%, 10%': {
                    opacity: 0.15,
                    transform: 'translate(1px, -1px)',
                  },
                  '45%, 48%': {
                    opacity: 0.1,
                    transform: 'translate(-1px, 1px)',
                  }
                },
                '@keyframes raptorLoginHoverShimmer1': {
                  '0%, 100%': {
                    opacity: 0.4,
                    transform: 'translate(2px, 2px)',
                  },
                  '50%': {
                    opacity: 0.2,
                    transform: 'translate(-1px, 1px)',
                  }
                },
                '@keyframes raptorLoginHoverShimmer2': {
                  '0%, 100%': {
                    opacity: 0.3,
                    transform: 'translate(-2px, -2px)',
                  },
                  '50%': {
                    opacity: 0.15,
                    transform: 'translate(1px, -1px)',
                  }
                }
              }}
            >
              RAPTOR
            </Typography>
            <Typography 
              variant="subtitle1" 
              sx={{ 
                color: 'text.secondary',
                letterSpacing: '0.05em',
                textAlign: 'center',
                fontSize: '0.9rem',
                mb: 4
              }}
            >
              Reconnaissance, Assessment, Penetration Testing, Operations & Reporting
            </Typography>
          </Box>

          {/* Login / Reset Form */}
          {resetMode ? (
            <Box component="form" onSubmit={handleResetSubmit} sx={{ mt: 3 }}>
              {resetError && (
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
                  {resetError}
                </Alert>
              )}

              <TextField
                fullWidth
                label="Username"
                variant="outlined"
                value={username}
                disabled
                autoComplete="username"
                sx={{ 
                  mb: 3,
                  '& .MuiOutlinedInput-root': {
                    backgroundColor: darkMode ? 'rgba(255,255,255,0.05)' : 'background.paper',
                    '& fieldset': {
                      borderColor: theme.palette.divider,
                    },
                  },
                }}
              />

              <TextField
                fullWidth
                label="New Password"
                type={showPassword ? 'text' : 'password'}
                variant="outlined"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                autoComplete="new-password"
                sx={{ 
                  mb: 2,
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

              <TextField
                fullWidth
                label="Confirm New Password"
                type={showPassword ? 'text' : 'password'}
                variant="outlined"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
                sx={{ 
                  mb: 2,
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

              <Box sx={{ textAlign: 'left', mb: 3 }}>
                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                  NIST password requirements:
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  - At least {MIN_PASSWORD_LENGTH} characters (max {MAX_PASSWORD_LENGTH})
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  - Not a common password
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  - Must not contain the username
                </Typography>
              </Box>

              <Button
                type="submit"
                fullWidth
                variant="contained"
                disabled={resetLoading || !newPassword || !confirmPassword}
                startIcon={<LoginOutlined />}
                sx={{ mb: 2 }}
              >
                {resetLoading ? 'Updating password...' : 'Reset Password'}
              </Button>
            </Box>
          ) : (
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
          )}

          {/* Footer */}
          <Box mt={4}>
            <Typography variant="caption" color="text.secondary">
            </Typography>
          </Box>
        </Paper>
      </Box>
  );
};

export default ModernLogin;
