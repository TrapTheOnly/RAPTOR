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
            sx={{ 
              fontWeight: 300,
              letterSpacing: '-0.02em',
              color: theme.palette.text.primary
            }}
          >
            DNS<span style={{ fontWeight: 600 }}>Radar</span>
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