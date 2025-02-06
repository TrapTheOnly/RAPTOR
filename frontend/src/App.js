import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axios from 'axios';
import Login from './components/Login';
import RecordsTable from './components/RecordsTable';
import Header from './components/Header';
import Settings from './components/Settings';
import RecordDetail from './components/RecordDetail';
import ErrorPage from './components/ErrorPage';

const App = () => {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(true);
  const [userRole, setUserRole] = useState(null);
  const storedTheme = localStorage.getItem('theme') || 'light';
  const [darkMode, setDarkMode] = useState(storedTheme === 'dark');

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

  useEffect(() => {
    localStorage.setItem('theme', darkMode ? 'dark' : 'light');
  }, [darkMode]);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Router>
        {loggedIn && (
          <Header
            username={username}
            userRole={userRole}
            setUserRole={setUserRole}
            setLoggedIn={setLoggedIn}
            setUsername={setUsername}
            darkMode={darkMode}
            setDarkMode={setDarkMode}
          />
        )}
      <Routes>
        <Route
          path="/"
          element={loggedIn && userRole ? 
            <RecordsTable userRole={userRole} darkMode={darkMode}/> : 
              <Navigate to="/login" />}
        />
        <Route
          path="/login"
          element={ !loggedIn ?
            <Login
              setLoggedIn={setLoggedIn}
              setGlobalUsername={setUsername}
              setGlobalUserRole={setUserRole}
              darkMode={darkMode}
              setDarkMode={setDarkMode}
            /> : <Navigate to="/" />
          }
        />
        <Route
          path="/settings"
          element={
            loggedIn && userRole === "admin" ? 
              <Settings darkMode={darkMode}/> : 
                <Navigate to="/" />
          }
        />
        <Route
          path="/records/:domain"
          element={loggedIn ? <RecordDetail darkMode={darkMode} /> : <Navigate to="/login" />}
        />
        <Route path="/records/*" element={<Navigate to="/" />} />
        <Route path="*" element={<ErrorPage errorCode={404} errorMessage="Page Not Found" darkMode={darkMode}/>} />
      </Routes>
    </Router>
  );
};

export default App;