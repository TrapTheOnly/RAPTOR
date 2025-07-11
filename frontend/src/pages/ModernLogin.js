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
              variant="h3" 
              sx={{ 
                fontWeight: 700,
                fontSize: '2.5rem',
                letterSpacing: '0.15em',
                background: 'linear-gradient(45deg, #00d4ff 30%, #1976d2 90%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
                mb: 1,
                textAlign: 'center',
                position: 'relative',
                display: 'inline-block',
                transform: 'perspective(1000px)',
                transformStyle: 'preserve-3d',
                animation: 'raptorMainGlow 3s ease-in-out infinite alternate, raptorFloat 6s ease-in-out infinite',
                '&::before': {
                  content: '"RAPTOR"',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  background: 'linear-gradient(45deg, #ff4081 30%, #e91e63 90%)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  color: 'transparent',
                  opacity: 0,
                  transform: 'translate(3px, 3px) rotateX(5deg)',
                  animation: 'raptorMainGlitch1 4s infinite, raptorMainShift1 8s ease-in-out infinite',
                  zIndex: -1,
                  filter: 'blur(0.5px)',
                },
                '&::after': {
                  content: '"RAPTOR"',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: '100%',
                  background: 'linear-gradient(45deg, #00ff88 30%, #4caf50 90%)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  color: 'transparent',
                  opacity: 0,
                  transform: 'translate(-3px, -3px) rotateX(-5deg)',
                  animation: 'raptorMainGlitch2 4s infinite 1s, raptorMainShift2 8s ease-in-out infinite 1s',
                  zIndex: -2,
                  filter: 'blur(0.5px)',
                },
                '&:hover': {
                  animation: 'raptorMainHover 0.8s ease-out, raptorMainGlow 1s ease-in-out infinite alternate',
                  transform: 'perspective(1000px) rotateX(10deg) rotateY(-10deg) scale(1.1)',
                  filter: 'drop-shadow(0 15px 30px rgba(0, 212, 255, 0.4))',
                  '&::before': {
                    animation: 'raptorMainGlitchHover1 0.2s infinite, raptorMainShift1 4s ease-in-out infinite',
                  },
                  '&::after': {
                    animation: 'raptorMainGlitchHover2 0.2s infinite 0.1s, raptorMainShift2 4s ease-in-out infinite 0.5s',
                  }
                },
                '@keyframes raptorMainGlow': {
                  '0%': {
                    textShadow: `
                      0 0 10px rgba(0, 212, 255, 0.6),
                      0 0 20px rgba(0, 212, 255, 0.4),
                      0 0 30px rgba(25, 118, 210, 0.3),
                      0 0 40px rgba(25, 118, 210, 0.1)
                    `,
                    filter: 'brightness(1) saturate(1)',
                  },
                  '50%': {
                    textShadow: `
                      0 0 15px rgba(0, 212, 255, 0.8),
                      0 0 30px rgba(0, 212, 255, 0.6),
                      0 0 45px rgba(25, 118, 210, 0.5),
                      0 0 60px rgba(25, 118, 210, 0.3)
                    `,
                    filter: 'brightness(1.3) saturate(1.2)',
                  },
                  '100%': {
                    textShadow: `
                      0 0 10px rgba(0, 212, 255, 0.6),
                      0 0 20px rgba(0, 212, 255, 0.4),
                      0 0 30px rgba(25, 118, 210, 0.3),
                      0 0 40px rgba(25, 118, 210, 0.1)
                    `,
                    filter: 'brightness(1) saturate(1)',
                  }
                },
                '@keyframes raptorFloat': {
                  '0%, 100%': {
                    transform: 'perspective(1000px) translateY(0px) rotateX(0deg)',
                  },
                  '25%': {
                    transform: 'perspective(1000px) translateY(-3px) rotateX(2deg)',
                  },
                  '50%': {
                    transform: 'perspective(1000px) translateY(-5px) rotateX(0deg)',
                  },
                  '75%': {
                    transform: 'perspective(1000px) translateY(-3px) rotateX(-2deg)',
                  }
                },
                '@keyframes raptorMainGlitch1': {
                  '0%, 85%, 100%': {
                    opacity: 0,
                    transform: 'translate(3px, 3px) rotateX(5deg)',
                    clipPath: 'inset(0 0 0 0)',
                  },
                  '2%, 4%': {
                    opacity: 0.9,
                    transform: 'translate(-5px, 2px) rotateX(8deg) skew(2deg)',
                    clipPath: 'inset(20% 0 30% 0)',
                  },
                  '6%, 8%': {
                    opacity: 0.7,
                    transform: 'translate(2px, -4px) rotateX(-3deg) skew(-1deg)',
                    clipPath: 'inset(60% 0 10% 0)',
                  },
                  '10%, 12%': {
                    opacity: 0.8,
                    transform: 'translate(-3px, 3px) rotateX(6deg) skew(1deg)',
                    clipPath: 'inset(40% 0 50% 0)',
                  },
                  '15%, 17%': {
                    opacity: 0.6,
                    transform: 'translate(4px, -2px) rotateX(-4deg) skew(-2deg)',
                    clipPath: 'inset(10% 0 70% 0)',
                  }
                },
                '@keyframes raptorMainGlitch2': {
                  '0%, 90%, 100%': {
                    opacity: 0,
                    transform: 'translate(-3px, -3px) rotateX(-5deg)',
                    clipPath: 'inset(0 0 0 0)',
                  },
                  '3%, 6%': {
                    opacity: 0.8,
                    transform: 'translate(4px, -3px) rotateX(-8deg) skew(-2deg)',
                    clipPath: 'inset(30% 0 20% 0)',
                  },
                  '8%, 11%': {
                    opacity: 0.6,
                    transform: 'translate(-2px, 4px) rotateX(4deg) skew(1deg)',
                    clipPath: 'inset(50% 0 40% 0)',
                  },
                  '13%, 16%': {
                    opacity: 0.9,
                    transform: 'translate(3px, -3px) rotateX(-6deg) skew(-1deg)',
                    clipPath: 'inset(70% 0 15% 0)',
                  },
                  '18%, 21%': {
                    opacity: 0.5,
                    transform: 'translate(-4px, 2px) rotateX(3deg) skew(2deg)',
                    clipPath: 'inset(15% 0 60% 0)',
                  }
                },
                '@keyframes raptorMainShift1': {
                  '0%, 100%': {
                    background: 'linear-gradient(45deg, #ff4081 30%, #e91e63 90%)',
                  },
                  '25%': {
                    background: 'linear-gradient(45deg, #ff6b9d 30%, #f06292 90%)',
                  },
                  '50%': {
                    background: 'linear-gradient(45deg, #ff8a80 30%, #ff5722 90%)',
                  },
                  '75%': {
                    background: 'linear-gradient(45deg, #ff7043 30%, #e64a19 90%)',
                  }
                },
                '@keyframes raptorMainShift2': {
                  '0%, 100%': {
                    background: 'linear-gradient(45deg, #00ff88 30%, #4caf50 90%)',
                  },
                  '25%': {
                    background: 'linear-gradient(45deg, #69f0ae 30%, #00e676 90%)',
                  },
                  '50%': {
                    background: 'linear-gradient(45deg, #81c784 30%, #66bb6a 90%)',
                  },
                  '75%': {
                    background: 'linear-gradient(45deg, #a5d6a7 30%, #8bc34a 90%)',
                  }
                },
                '@keyframes raptorMainHover': {
                  '0%': {
                    transform: 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)',
                  },
                  '20%': {
                    transform: 'perspective(1000px) rotateX(20deg) rotateY(-20deg) scale(1.15)',
                  },
                  '40%': {
                    transform: 'perspective(1000px) rotateX(-10deg) rotateY(10deg) scale(1.12)',
                  },
                  '60%': {
                    transform: 'perspective(1000px) rotateX(15deg) rotateY(-15deg) scale(1.08)',
                  },
                  '80%': {
                    transform: 'perspective(1000px) rotateX(5deg) rotateY(-5deg) scale(1.05)',
                  },
                  '100%': {
                    transform: 'perspective(1000px) rotateX(10deg) rotateY(-10deg) scale(1.1)',
                  }
                },
                '@keyframes raptorMainGlitchHover1': {
                  '0%, 100%': {
                    opacity: 0,
                    transform: 'translate(3px, 3px) rotateX(5deg) skew(0deg)',
                  },
                  '10%': {
                    opacity: 1,
                    transform: 'translate(-8px, 5px) rotateX(12deg) skew(3deg)',
                  },
                  '20%': {
                    opacity: 0.8,
                    transform: 'translate(6px, -7px) rotateX(-8deg) skew(-2deg)',
                  },
                  '30%': {
                    opacity: 0.9,
                    transform: 'translate(-4px, 4px) rotateX(10deg) skew(1deg)',
                  },
                  '40%': {
                    opacity: 0.7,
                    transform: 'translate(7px, -3px) rotateX(-6deg) skew(-3deg)',
                  },
                  '50%': {
                    opacity: 0.85,
                    transform: 'translate(-5px, 6px) rotateX(8deg) skew(2deg)',
                  },
                  '60%': {
                    opacity: 0.6,
                    transform: 'translate(8px, -5px) rotateX(-10deg) skew(-1deg)',
                  },
                  '70%': {
                    opacity: 0.9,
                    transform: 'translate(-6px, 3px) rotateX(7deg) skew(3deg)',
                  },
                  '80%': {
                    opacity: 0.75,
                    transform: 'translate(5px, -6px) rotateX(-9deg) skew(-2deg)',
                  },
                  '90%': {
                    opacity: 0.8,
                    transform: 'translate(-7px, 4px) rotateX(11deg) skew(1deg)',
                  }
                },
                '@keyframes raptorMainGlitchHover2': {
                  '0%, 100%': {
                    opacity: 0,
                    transform: 'translate(-3px, -3px) rotateX(-5deg) skew(0deg)',
                  },
                  '15%': {
                    opacity: 0.9,
                    transform: 'translate(7px, -6px) rotateX(-12deg) skew(-3deg)',
                  },
                  '25%': {
                    opacity: 0.7,
                    transform: 'translate(-5px, 8px) rotateX(9deg) skew(2deg)',
                  },
                  '35%': {
                    opacity: 0.85,
                    transform: 'translate(4px, -4px) rotateX(-10deg) skew(-1deg)',
                  },
                  '45%': {
                    opacity: 0.6,
                    transform: 'translate(-8px, 5px) rotateX(7deg) skew(3deg)',
                  },
                  '55%': {
                    opacity: 0.8,
                    transform: 'translate(6px, -7px) rotateX(-8deg) skew(-2deg)',
                  },
                  '65%': {
                    opacity: 0.75,
                    transform: 'translate(-5px, 6px) rotateX(9deg) skew(1deg)',
                  },
                  '75%': {
                    opacity: 0.9,
                    transform: 'translate(7px, -4px) rotateX(-11deg) skew(-3deg)',
                  },
                  '85%': {
                    opacity: 0.65,
                    transform: 'translate(-6px, 7px) rotateX(8deg) skew(2deg)',
                  },
                  '95%': {
                    opacity: 0.8,
                    transform: 'translate(5px, -5px) rotateX(-7deg) skew(-1deg)',
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