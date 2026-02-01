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
    { label: 'Dashboard', path: '/', icon: Dashboard, roles: ['admin', 'pentester', 'manager'] },
    { label: 'Records', path: '/records', icon: TableView, roles: ['admin', 'user', 'pentester', 'manager'] },
    { label: 'Security', path: '/pentest', icon: Security, roles: ['admin', 'pentester', 'user', 'manager'] },
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
      case 'manager': return '#00897B';
      default: return '#666666';
    }
  };

  return (
    <AppBar 
      position="sticky" 
      elevation={0}
      sx={{ 
        backgroundColor: theme.palette.background.paper,
        borderBottom: `1px solid ${theme.palette.divider}`,
        top: 0,
        zIndex: theme.zIndex.drawer + 1
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
              background: theme.palette.mode === 'dark' 
                ? 'linear-gradient(45deg, #00d4ff 30%, #1976d2 90%)'
                : 'linear-gradient(45deg, #1976d2 30%, #0d47a1 90%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              color: 'transparent',
              position: 'relative',
              display: 'inline-block',
              transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
              animation: 'raptorGentleGlow 6s ease-in-out infinite alternate',
              '&::before': {
                content: '"RAPTOR"',
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                background: theme.palette.mode === 'dark'
                  ? 'linear-gradient(45deg, rgba(255, 64, 129, 0.3) 30%, rgba(233, 30, 99, 0.3) 90%)'
                  : 'linear-gradient(45deg, rgba(25, 118, 210, 0.2) 30%, rgba(13, 71, 161, 0.2) 90%)',
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
                opacity: 0,
                transform: 'translate(1px, 1px)',
                animation: 'raptorSubtleShimmer 8s ease-in-out infinite',
                zIndex: -1,
              },
              '&::after': {
                content: '""',
                position: 'absolute',
                bottom: '-2px',
                left: '0',
                width: '0%',
                height: '2px',
                background: theme.palette.mode === 'dark'
                  ? 'linear-gradient(90deg, transparent, #00d4ff, transparent)'
                  : 'linear-gradient(90deg, transparent, #1976d2, transparent)',
                transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
                zIndex: -1,
              },
              '&:hover': {
                transform: 'translateY(-1px) scale(1.02)',
                filter: theme.palette.mode === 'dark'
                  ? 'drop-shadow(0 4px 12px rgba(0, 212, 255, 0.15))'
                  : 'drop-shadow(0 4px 12px rgba(25, 118, 210, 0.15))',
                '&::before': {
                  opacity: 0.6,
                  animation: 'raptorHoverShimmer 2s ease-in-out infinite',
                },
                '&::after': {
                  width: '100%',
                }
              },
              '@keyframes raptorGentleGlow': {
                '0%': {
                  textShadow: theme.palette.mode === 'dark'
                    ? '0 0 8px rgba(0, 212, 255, 0.3)'
                    : '0 0 8px rgba(25, 118, 210, 0.2)',
                  filter: 'brightness(1)',
                },
                '50%': {
                  textShadow: theme.palette.mode === 'dark'
                    ? '0 0 12px rgba(0, 212, 255, 0.5), 0 0 24px rgba(25, 118, 210, 0.2)'
                    : '0 0 12px rgba(25, 118, 210, 0.4), 0 0 24px rgba(13, 71, 161, 0.1)',
                  filter: 'brightness(1.1)',
                },
                '100%': {
                  textShadow: theme.palette.mode === 'dark'
                    ? '0 0 8px rgba(0, 212, 255, 0.3)'
                    : '0 0 8px rgba(25, 118, 210, 0.2)',
                  filter: 'brightness(1)',
                }
              },
              '@keyframes raptorSubtleShimmer': {
                '0%, 90%, 100%': {
                  opacity: 0,
                  transform: 'translate(1px, 1px)',
                },
                '5%, 8%': {
                  opacity: 0.3,
                  transform: 'translate(-1px, 0.5px)',
                },
                '45%, 48%': {
                  opacity: 0.2,
                  transform: 'translate(0.5px, -1px)',
                }
              },
              '@keyframes raptorHoverShimmer': {
                '0%, 100%': {
                  opacity: 0.6,
                  transform: 'translate(1px, 1px)',
                },
                '50%': {
                  opacity: 0.4,
                  transform: 'translate(-0.5px, 0.5px)',
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
