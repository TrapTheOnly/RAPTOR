import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  IconButton,
  Avatar,
  Menu,
  MenuItem,
  Divider,
  Chip,
  Button,
  useTheme,
  alpha
} from '@mui/material';
import {
  Dashboard,
  TableView,
  Security,
  Settings,
  Logout,
  Person,
  Brightness4,
  Brightness7
} from '@mui/icons-material';

const ModernHeader = ({ 
  username, 
  userRole, 
  setUserRole, 
  setLoggedIn, 
  setUsername,
  darkMode,
  setDarkMode
}) => {
  const [anchorEl, setAnchorEl] = useState(null);
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();

  const handleProfileMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    try {
      await axios.post('/logout');
      setLoggedIn(false);
      setUsername('');
      setUserRole(null);
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
    }
    handleMenuClose();
  };

  const navigationItems = [
    { label: 'Dashboard', path: '/', icon: Dashboard, roles: ['admin', 'pentester'] },
    { label: 'Records', path: '/records', icon: TableView, roles: ['admin', 'user', 'pentester'] },
    { label: 'Security', path: '/pentest', icon: Security, roles: ['admin', 'pentester'] },
    { label: 'Settings', path: '/settings', icon: Settings, roles: ['admin'] },
  ];

  const visibleNavItems = navigationItems.filter(item => 
    item.roles.includes(userRole)
  );

  const isActive = (path) => {
    if (path === '/' && location.pathname === '/') return true;
    if (path !== '/' && location.pathname.startsWith(path)) return true;
    return false;
  };

  const getRoleColor = (role) => {
    switch (role) {
      case 'admin': return '#F44336';
      case 'pentester': return '#FF9800';
      case 'user': return '#4CAF50';
      default: return '#666666';
    }
  };

  return (
    <AppBar 
      position="static" 
      elevation={0}
      sx={{ 
        backgroundColor: theme.palette.background.paper,
        borderBottom: `1px solid ${theme.palette.divider}`,
      }}
    >
      <Toolbar sx={{ justifyContent: 'space-between', py: 1 }}>
        {/* Logo/Brand */}
        <Box display="flex" alignItems="center">
          <Typography 
            variant="h6" 
            onClick={() => navigate('/')}
            sx={{ 
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '1.5rem',
              letterSpacing: '0.1em',
              background: 'linear-gradient(45deg, #00d4ff 30%, #1976d2 90%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              color: 'transparent',
              position: 'relative',
              display: 'inline-block',
              transition: 'all 0.3s ease',
              animation: 'raptorGlow 4s ease-in-out infinite alternate',
              '&::before': {
                content: '"RAPTOR"',
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                background: 'linear-gradient(45deg, #ff1976 30%, #ff4081 90%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
                opacity: 0,
                transform: 'translate(2px, 2px)',
                animation: 'raptorGlitch 3s infinite',
                zIndex: -1,
              },
              '&::after': {
                content: '"RAPTOR"',
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                background: 'linear-gradient(45deg, #00ff88 30%, #00e676 90%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
                opacity: 0,
                transform: 'translate(-2px, -2px)',
                animation: 'raptorGlitch2 3s infinite 0.5s',
                zIndex: -2,
              },
              '&:hover': {
                transform: 'perspective(1000px) rotateX(10deg) rotateY(-10deg) scale(1.05)',
                filter: 'drop-shadow(0 10px 20px rgba(0, 212, 255, 0.3))',
                animation: 'raptorIntense 0.6s ease-out',
                '&::before': {
                  animation: 'raptorGlitchIntense 0.3s infinite',
                },
                '&::after': {
                  animation: 'raptorGlitchIntense2 0.3s infinite 0.1s',
                }
              },
              '@keyframes raptorGlow': {
                '0%': {
                  textShadow: '0 0 5px rgba(0, 212, 255, 0.5), 0 0 10px rgba(0, 212, 255, 0.3)',
                  filter: 'brightness(1)',
                },
                '50%': {
                  textShadow: '0 0 10px rgba(0, 212, 255, 0.8), 0 0 20px rgba(0, 212, 255, 0.6), 0 0 30px rgba(25, 118, 210, 0.4)',
                  filter: 'brightness(1.2)',
                },
                '100%': {
                  textShadow: '0 0 5px rgba(0, 212, 255, 0.5), 0 0 10px rgba(0, 212, 255, 0.3)',
                  filter: 'brightness(1)',
                }
              },
              '@keyframes raptorGlitch': {
                '0%, 90%, 100%': {
                  opacity: 0,
                  transform: 'translate(2px, 2px)',
                },
                '2%, 5%': {
                  opacity: 0.8,
                  transform: 'translate(-3px, 1px)',
                },
                '10%, 15%': {
                  opacity: 0.6,
                  transform: 'translate(1px, -2px)',
                },
                '20%, 25%': {
                  opacity: 0.9,
                  transform: 'translate(2px, 3px)',
                }
              },
              '@keyframes raptorGlitch2': {
                '0%, 85%, 100%': {
                  opacity: 0,
                  transform: 'translate(-2px, -2px)',
                },
                '3%, 8%': {
                  opacity: 0.7,
                  transform: 'translate(3px, -1px)',
                },
                '12%, 18%': {
                  opacity: 0.5,
                  transform: 'translate(-1px, 2px)',
                },
                '22%, 28%': {
                  opacity: 0.8,
                  transform: 'translate(-2px, -3px)',
                }
              },
              '@keyframes raptorIntense': {
                '0%': {
                  transform: 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale(1)',
                },
                '20%': {
                  transform: 'perspective(1000px) rotateX(15deg) rotateY(-15deg) scale(1.1)',
                },
                '40%': {
                  transform: 'perspective(1000px) rotateX(-5deg) rotateY(5deg) scale(1.08)',
                },
                '60%': {
                  transform: 'perspective(1000px) rotateX(8deg) rotateY(-8deg) scale(1.06)',
                },
                '100%': {
                  transform: 'perspective(1000px) rotateX(10deg) rotateY(-10deg) scale(1.05)',
                }
              },
              '@keyframes raptorGlitchIntense': {
                '0%, 100%': {
                  opacity: 0,
                  transform: 'translate(2px, 2px) skew(0deg)',
                },
                '20%': {
                  opacity: 1,
                  transform: 'translate(-5px, 3px) skew(2deg)',
                },
                '40%': {
                  opacity: 0.8,
                  transform: 'translate(3px, -4px) skew(-1deg)',
                },
                '60%': {
                  opacity: 0.9,
                  transform: 'translate(-2px, 2px) skew(1deg)',
                },
                '80%': {
                  opacity: 0.7,
                  transform: 'translate(4px, -1px) skew(-2deg)',
                }
              },
              '@keyframes raptorGlitchIntense2': {
                '0%, 100%': {
                  opacity: 0,
                  transform: 'translate(-2px, -2px) skew(0deg)',
                },
                '25%': {
                  opacity: 0.9,
                  transform: 'translate(4px, -3px) skew(-2deg)',
                },
                '45%': {
                  opacity: 0.6,
                  transform: 'translate(-3px, 4px) skew(1deg)',
                },
                '65%': {
                  opacity: 0.8,
                  transform: 'translate(2px, -2px) skew(2deg)',
                },
                '85%': {
                  opacity: 0.7,
                  transform: 'translate(-4px, 1px) skew(-1deg)',
                }
              }
            }}
          >
            RAPTOR
          </Typography>
        </Box>

        {/* Navigation */}
        <Box display="flex" alignItems="center" gap={0.5}>
          {visibleNavItems.map((item) => (
            <Button
              key={item.path}
              onClick={() => navigate(item.path)}
              startIcon={<item.icon />}
              sx={{
                color: isActive(item.path) ? theme.palette.text.primary : theme.palette.text.secondary,
                backgroundColor: isActive(item.path) ? alpha(theme.palette.text.primary, 0.1) : 'transparent',
                textTransform: 'none',
                px: 2,
                py: 1,
                borderRadius: 1,
                fontWeight: isActive(item.path) ? 500 : 400,
                '&:hover': {
                  backgroundColor: alpha(theme.palette.text.primary, 0.05),
                  color: theme.palette.text.primary,
                },
                transition: 'all 0.2s ease-in-out',
              }}
            >
              {item.label}
            </Button>
          ))}
        </Box>

        {/* User Profile & Theme Switcher */}
        <Box display="flex" alignItems="center" gap={2}>
          <IconButton 
            sx={{ color: theme.palette.text.secondary }} 
            onClick={() => setDarkMode(!darkMode)}
            title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {darkMode ? <Brightness7 /> : <Brightness4 />}
          </IconButton>
          <Box display="flex" alignItems="center" gap={1}>
            <Chip
              label={userRole}
              size="small"
              sx={{
                backgroundColor: getRoleColor(userRole),
                color: 'white',
                fontSize: '0.75rem',
                height: 20,
                '& .MuiChip-label': {
                  px: 1,
                },
              }}
            />
            <Typography variant="body2" color={theme.palette.text.secondary} sx={{ display: { xs: 'none', sm: 'block' } }}>
              {username}
            </Typography>
          </Box>
          
          <IconButton
            onClick={handleProfileMenuOpen}
            sx={{ 
              color: theme.palette.text.secondary,
              '&:hover': { color: theme.palette.text.primary },
            }}
          >
            <Avatar 
              sx={{ 
                width: 32, 
                height: 32, 
                backgroundColor: getRoleColor(userRole),
                fontSize: '0.875rem',
                fontWeight: 500,
              }}
            >
              {username.charAt(0).toUpperCase()}
            </Avatar>
          </IconButton>
        </Box>

        {/* Profile Menu */}
        <Menu
          anchorEl={anchorEl}
          open={Boolean(anchorEl)}
          onClose={handleMenuClose}
          PaperProps={{
            sx: {
              backgroundColor: theme.palette.background.paper,
              border: `1px solid ${theme.palette.divider}`,
              minWidth: 200,
              '& .MuiMenuItem-root': {
                color: theme.palette.text.primary,
                '&:hover': {
                  backgroundColor: alpha(theme.palette.text.primary, 0.05),
                },
              },
            },
          }}
          transformOrigin={{ horizontal: 'right', vertical: 'top' }}
          anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        >
          <MenuItem disabled>
            <Box>
              <Typography variant="body2" sx={{ fontWeight: 500 }}>
                {username}
              </Typography>
              <Typography variant="caption" color={theme.palette.text.secondary}>
                {userRole}
              </Typography>
            </Box>
          </MenuItem>
          <Divider sx={{ borderColor: theme.palette.divider }} />
          <MenuItem onClick={handleLogout}>
            <Logout sx={{ mr: 1, fontSize: 20 }} />
            Logout
          </MenuItem>
        </Menu>
      </Toolbar>
    </AppBar>
  );
};

export default ModernHeader;