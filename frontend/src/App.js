import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import axios from 'axios';
import ModernHeader from './components/ModernHeader';
import ModernLogin from './pages/ModernLogin';
import Dashboard from './pages/Dashboard';
import RecordsTable from './pages/RecordsTable';
import AdminSettings from './pages/AdminSettings';
import PentestDashboard from './pages/PentestDashboard';
import Record from './pages/Record';
import PentestRecord from './pages/PentestRecord';
import Error from './pages/Error';

const ROLE_DEFAULT_PERMISSIONS = {
  user: ['view_records', 'modify_records', 'view_record_details', 'export_records'],
  pentester: [
    'view_records',
    'view_security_dashboard',
    'view_record_details',
    'export_records',
    'view_pentest_page',
    'modify_pentests',
    'export_pentests'
  ],
  manager: [
    'view_settings',
    'view_dashboard',
    'view_records',
    'view_security_dashboard',
    'modify_records',
    'view_record_details',
    'export_records',
    'manage_ip_sources',
    'manage_vuln_categories',
    'manage_report_templates',
    'manage_apps',
    'view_pentest_page',
    'modify_pentests',
    'export_pentests',
    'reassign_pentests_admin',
    'delete_records',
    'modify_others_pentests_admin'
  ],
  admin: ['*']
};

const App = () => {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(true);
  const [userRole, setUserRole] = useState(null);
  const [userPermissions, setUserPermissions] = useState([]);
  const [passwordResetRequired, setPasswordResetRequired] = useState(false);
  const [resetUserType, setResetUserType] = useState(null);
  const storedTheme = localStorage.getItem('theme') || 'light';
  const [darkMode, setDarkMode] = useState(storedTheme === 'dark');

  const hasPermission = (permission) => {
    if (userRole === 'admin') return true;
    const normalizedRole = String(userRole || '').trim().toLowerCase();
    const roleDefaults = ROLE_DEFAULT_PERMISSIONS[normalizedRole] || [];
    if (roleDefaults.includes('*') || roleDefaults.includes(permission)) return true;
    return userPermissions?.includes(permission);
  };

  const getDefaultRoute = () => {
    if (!loggedIn) return '/login';

    // Strict role-first routing (requested behavior).
    const normalizedRole = String(userRole || '').trim().toLowerCase();
    if (normalizedRole === 'admin' || normalizedRole === 'manager') return '/dashboard';
    if (normalizedRole === 'pentester') return '/pentest';
    return '/records';
  };

  // Global theme for the entire application
  const globalTheme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: darkMode ? '#ffffff' : '#1976d2',
      },
      secondary: {
        main: darkMode ? '#666666' : '#9c27b0',
      },
      background: {
        default: darkMode ? '#0a0a0a' : '#f5f5f5',
        paper: darkMode ? '#141414' : '#ffffff',
      },
      text: {
        primary: darkMode ? '#ffffff' : '#333333',
        secondary: darkMode ? '#999999' : '#666666',
      },
      divider: darkMode ? '#333333' : '#e0e0e0',
    },
    typography: {
      fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
      h4: {
        fontWeight: 300,
        letterSpacing: '-0.025em',
      },
      h6: {
        fontWeight: 500,
        letterSpacing: '-0.01em',
      },
    },
    shape: {
      borderRadius: 8,
    },
  });

  useEffect(() => {
    const checkLoginStatus = async () => {
      try {
        const response = await axios.get('/session-status');
        if (response.status === 200) {
          if (response.data.status === 'password_reset_required') {
            setLoggedIn(false);
            setPasswordResetRequired(true);
            setUsername(response.data.username || '');
            setResetUserType(response.data.user_type || null);
            setUserRole(null);
            setUserPermissions(response.data.permissions || []);
          } else if (response.data.status === 'logged_in') {
            setLoggedIn(true);
            setPasswordResetRequired(false);
            setUsername(response.data.username);
            setUserRole(response.data.user_type);
            setResetUserType(null);
            setUserPermissions(response.data.permissions || []);
          }
        }
      } catch (error) {
        console.error("User is not logged in:", error);
        setLoggedIn(false);
        setPasswordResetRequired(false);
        setResetUserType(null);
        setUsername('');
        setUserRole(null);
        setUserPermissions([]);
      } finally {
        setLoading(false);
      }
    };

    checkLoginStatus();
  }, []);

  useEffect(() => {
    localStorage.setItem('theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  if (loading) {
    return (
      <ThemeProvider theme={globalTheme}>
        <CssBaseline />
        <div>Loading...</div>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={globalTheme}>
      <CssBaseline />
    <Router>
        {loggedIn && (
          <ModernHeader
            username={username}
            userRole={userRole}
            userPermissions={userPermissions}
            setUserRole={setUserRole}
            setLoggedIn={setLoggedIn}
            setUsername={setUsername}
              darkMode={darkMode}
              setDarkMode={setDarkMode}
            setUserPermissions={setUserPermissions}
          />
        )}
      <Routes>
        <Route
          path="/"
          element={loggedIn ? <Navigate to={getDefaultRoute()} replace /> : <Navigate to="/login" replace />}
        />
        <Route
          path="/dashboard"
          element={loggedIn && hasPermission('view_dashboard') ? 
            <Dashboard userRole={userRole} userPermissions={userPermissions} /> : 
              <Navigate to={loggedIn ? getDefaultRoute() : "/login"} replace />}
        />
        <Route
          path="/records"
          element={loggedIn && hasPermission('view_records') ? 
            <RecordsTable userRole={userRole} userPermissions={userPermissions} darkMode={darkMode}/> : 
              <Navigate to="/login" />}
        />
        <Route
          path="/login"
          element={ !loggedIn ?
            <ModernLogin
              setLoggedIn={setLoggedIn}
              setGlobalUsername={setUsername}
              setGlobalUserRole={setUserRole}
              setGlobalUserPermissions={setUserPermissions}
              setPasswordResetRequired={setPasswordResetRequired}
              passwordResetRequired={passwordResetRequired}
              resetUsername={username}
              resetUserType={resetUserType}
              setResetUserType={setResetUserType}
              darkMode={darkMode}
            /> : <Navigate to={getDefaultRoute()} replace />
          }
        />
        <Route
          path="/settings"
          element={
            loggedIn && hasPermission('view_settings') ? 
              <AdminSettings
                darkMode={darkMode}
                userRole={userRole}
                userPermissions={userPermissions}
              /> : 
                <Navigate to={loggedIn ? getDefaultRoute() : "/login"} />
          }
        />
        <Route
            path="/pentest"
            element={loggedIn && hasPermission('view_security_dashboard') ?
                <PentestDashboard
                  darkMode={darkMode}
                  isAdmin={userRole === 'admin'}
                  username={username}
                  userRole={userRole}
                  userPermissions={userPermissions}
                /> : <Navigate to="/login" />
            }
        />
        <Route
          path="/pentest/record/:recordId"
          element={
            loggedIn && hasPermission('view_pentest_page') ?
              <PentestRecord darkMode={darkMode} userPermissions={userPermissions} userRole={userRole} username={username} /> :
              <Navigate to={loggedIn ? "/pentest" : "/login"} />
          }
        />
        <Route
          path="/records/record/:recordId"
          element={loggedIn && hasPermission('view_record_details') ? <Record darkMode={darkMode} userPermissions={userPermissions} userRole={userRole} /> : <Navigate to="/login" />}
        />
        <Route
          path="/records/:domain"
          element={loggedIn && hasPermission('view_record_details') ? <Record darkMode={darkMode} userPermissions={userPermissions} userRole={userRole} /> : <Navigate to="/login" />}
        />
        <Route path="/records/*" element={<Navigate to="/" />} />
        <Route path="*" element={<Error errorCode={404} errorMessage="Page Not Found" darkMode={darkMode}/>} />
      </Routes>
    </Router>
    </ThemeProvider>
  );
};

export default App;
