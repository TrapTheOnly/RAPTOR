import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import { ThemeProvider, createTheme, CssBaseline, Box } from '@mui/material';
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

// Import global theme transition styles
import './styles/theme-transitions.css';

const App = () => {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(true);
  const [userRole, setUserRole] = useState(null);
  const storedTheme = localStorage.getItem('theme') || 'light';
  const [darkMode, setDarkMode] = useState(storedTheme === 'dark');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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
          setLoggedIn(true);
          setUsername(response.data.username);
          setUserRole(response.data.user_type);
        }
      } catch (error) {
        console.error("User is not logged in:", error);
        setLoggedIn(false);
        setUsername('');
        setUserRole(null);
      } finally {
        setLoading(false);
      }
    };

    checkLoginStatus();
  }, []);

  // Update data-theme attribute on document element for CSS custom properties
  useEffect(() => {
    // Immediate theme change for synchronized transitions
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light');
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

  const routeTitleMap = {
    '/': 'Dashboard',
    '/records': 'Records',
    '/pentest': 'Security',
    '/settings': 'Settings',
  };

  const resolveTitle = (pathname) => {
    if (pathname.startsWith('/records/')) return 'Record Details';
    if (pathname.startsWith('/pentest/record')) return 'Security Test';
    return routeTitleMap[Object.keys(routeTitleMap).find((key) => pathname === key || pathname.startsWith(key))] || 'RAPTOR';
  };

  return (
    <ThemeProvider theme={globalTheme}>
      <CssBaseline />
      <Router>
        {loggedIn && (
          <ModernHeader
            username={username}
            userRole={userRole}
            setUserRole={setUserRole}
            setLoggedIn={setLoggedIn}
            setUsername={setUsername}
            darkMode={darkMode}
            setDarkMode={setDarkMode}
            pageTitle={resolveTitle(window.location.pathname)}
          />
        )}
        <Box sx={{ display: 'flex', pt: loggedIn ? 8 : 0 }}>
          <Box sx={{ flex: 1, px: loggedIn ? 4 : 0, py: loggedIn ? 3 : 0 }}>
            <Routes>
              <Route
                path="/"
                element={loggedIn && (userRole === 'pentester' || userRole === 'admin') ?
                  <Dashboard userRole={userRole} darkMode={darkMode}/> :
                  loggedIn ? <Navigate to="/records" /> : <Navigate to="/login" />}
              />
              <Route
                path="/records"
                element={loggedIn && userRole ?
                  <RecordsTable userRole={userRole} darkMode={darkMode}/> :
                  <Navigate to="/login" />}
              />
              <Route
                path="/login"
                element={ !loggedIn ?
                  <ModernLogin
                    setLoggedIn={setLoggedIn}
                    setGlobalUsername={setUsername}
                    setGlobalUserRole={setUserRole}
                    darkMode={darkMode}
                  /> : <Navigate to="/" />
                }
              />
              <Route
                path="/settings"
                element={
                  loggedIn && userRole === "admin" ?
                    <AdminSettings darkMode={darkMode}/> :
                    <Navigate to="/" />
                }
              />
              <Route
                path="/pentest"
                element={loggedIn && (userRole === 'pentester' || userRole === 'admin') ?
                  <PentestDashboard darkMode={darkMode} isAdmin={userRole === 'admin'} username={username}/> : <Navigate to="/login" />
                }
              />
              <Route
                path="/pentest/record/:recordId"
                element={loggedIn ? <PentestRecord darkMode={darkMode} /> : <Navigate to="/login" />}
              />
              <Route
                path="/records/:domain"
                element={loggedIn ? <Record darkMode={darkMode} /> : <Navigate to="/login" />}
              />
              <Route path="/records/*" element={<Navigate to="/" />} />
              <Route path="*" element={<Error errorCode={404} errorMessage="Page Not Found" darkMode={darkMode}/>} />
            </Routes>
          </Box>
        </Box>
      </Router>
    </ThemeProvider>
  );
};

export default App;
