import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation, Link as RouterLink } from 'react-router-dom';
import axios from 'axios';
import { Avatar, IconButton, Menu, MenuItem, Divider, Tooltip } from '@mui/material';
import { Brightness4, Brightness7, HelpOutline, Logout } from '@mui/icons-material';
import { LayoutGroup, motion } from 'motion/react';
import { hasPermission as hasRolePermission } from '../utils/permissions';
import NotificationBell from './NotificationBell';
import { CommandPalette, Mono, Tag, Text } from '../design/primitives';
import { LAYOUT, FONTS, SPACE } from '../design/tokens';
import { LAYOUT_ID, TRANSITION } from '../design/motion';
import { usePalette } from '../design/usePalette';

const ModernHeader = ({
  username,
  userRole,
  userPermissions,
  setUserRole,
  setLoggedIn,
  setUsername,
  darkMode,
  setDarkMode,
  setUserPermissions
}) => {
  const [anchorEl, setAnchorEl] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const palette = usePalette();

  const hasPermission = (permission) => hasRolePermission(userRole, userPermissions, permission);

  const getDefaultRoute = () => {
    const normalizedRole = String(userRole || '').trim().toLowerCase();
    if (normalizedRole === 'admin' || normalizedRole === 'manager') return '/dashboard';
    if (normalizedRole === 'pentester') return '/pentest';
    return '/records';
  };

  const navigationItems = [
    { label: 'Dashboard', path: '/dashboard', visible: hasPermission('view_dashboard') },
    { label: 'Records', path: '/records', visible: hasPermission('view_records') },
    { label: 'Security', path: '/pentest', visible: hasPermission('view_security_dashboard') },
    { label: 'Settings', path: '/settings', visible: hasPermission('view_settings') }
  ].filter((item) => item.visible);

  const isDocsRoute = location.pathname.startsWith('/docs');

  const isActive = (path) => {
    if (path === '/dashboard' && (location.pathname === '/' || location.pathname === '/dashboard')) return true;
    if (path === '/pentest' && location.pathname.startsWith('/apps')) return true;
    if (path !== '/' && location.pathname.startsWith(path)) return true;
    return false;
  };

  useEffect(() => {
    const onKey = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setPaletteOpen((open) => !open);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const handleLogout = async () => {
    try {
      await axios.post('/logout');
      setLoggedIn(false);
      setUsername('');
      setUserRole(null);
      setUserPermissions([]);
      navigate('/login');
    } catch (error) {
      console.error('Logout error:', error);
    }
    setAnchorEl(null);
  };

  return (
    <>
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          height: LAYOUT.navHeight,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: `0 ${SPACE.x16}px`,
          background: palette.surface,
          borderBottom: `1px solid ${palette.line}`
        }}
      >
        <button
          type="button"
          onClick={() => navigate(getDefaultRoute())}
          style={{
            background: 'transparent',
            border: 0,
            padding: 0,
            cursor: 'pointer',
            color: palette.text
          }}
        >
          <Mono style={{ fontSize: 14, fontWeight: 600, letterSpacing: '0.14em' }}>RAPTOR</Mono>
        </button>

        <LayoutGroup>
          <nav style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            {navigationItems.map((item) => {
              const active = isActive(item.path);
              return (
                <RouterLink
                  key={item.path}
                  to={item.path}
                  style={{
                    position: 'relative',
                    color: active ? palette.text : palette.textSecondary,
                    textDecoration: 'none',
                    fontFamily: FONTS.sans,
                    fontSize: 13,
                    fontWeight: 500,
                    padding: '8px 12px'
                  }}
                >
                  {item.label}
                  {active ? (
                    <motion.span
                      layoutId={LAYOUT_ID.navIndicator}
                      transition={TRANSITION.move}
                      style={{
                        position: 'absolute',
                        left: 12,
                        right: 12,
                        bottom: 0,
                        height: 1,
                        background: palette.accent
                      }}
                    />
                  ) : null}
                </RouterLink>
              );
            })}
          </nav>
        </LayoutGroup>

        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Tooltip title="Jump to (⌘K)">
            <IconButton
              size="small"
              onClick={() => setPaletteOpen(true)}
              aria-label="Open command palette"
            >
              <Text variant="micro" tone="secondary" as="span" style={{ padding: '0 4px' }}>
                ⌘K
              </Text>
            </IconButton>
          </Tooltip>
          <Tooltip title="Documentation">
            <IconButton
              size="small"
              onClick={() => navigate('/docs')}
              aria-label="Open documentation"
              style={{ color: isDocsRoute ? palette.text : palette.textSecondary }}
            >
              <HelpOutline fontSize="small" />
            </IconButton>
          </Tooltip>
          <NotificationBell username={username} />
          <IconButton
            size="small"
            onClick={() => setDarkMode(!darkMode)}
            title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {darkMode ? <Brightness7 fontSize="small" /> : <Brightness4 fontSize="small" />}
          </IconButton>
          <Tag>{userRole}</Tag>
          <IconButton size="small" onClick={(event) => setAnchorEl(event.currentTarget)}>
            <Avatar sx={{ width: 24, height: 24 }}>{username.charAt(0).toUpperCase()}</Avatar>
          </IconButton>
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={() => setAnchorEl(null)}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem disabled>
              <div>
                <Text as="div" variant="bodyStrong">
                  {username}
                </Text>
                <Text as="div" variant="meta" tone="secondary">
                  {userRole}
                </Text>
              </div>
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleLogout}>
              <Logout sx={{ mr: 1, fontSize: 18 }} />
              Logout
            </MenuItem>
          </Menu>
        </div>
      </header>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </>
  );
};

export default ModernHeader;
