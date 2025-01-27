import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axios from 'axios';
import Login from './components/Login';
import RecordsTable from './components/RecordsTable';
import Header from './components/Header';

const App = () => {
  const [loggedIn, setLoggedIn] = useState(false);
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkLoginStatus = async () => {
      try {
        const response = await axios.get('/session-status');
        if (response.status === 200) {
          setLoggedIn(true);
          setUsername(response.data.username);
        }
      } catch (error) {
        console.error("User is not logged in:", error);
        setLoggedIn(false);
        setUsername('');
      } finally {
        setLoading(false);
      }
    };

    checkLoginStatus();
  }, []);

  // Show a loading indicator until the login state is verified
  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Router>
      {loggedIn && <Header username={username} setLoggedIn={setLoggedIn} setUsername={setUsername} />}
      <Routes>
        <Route
          path="/"
          element={loggedIn ? <RecordsTable /> : <Navigate to="/login" />}
        />
        <Route
          path="/login"
          element={<Login setLoggedIn={setLoggedIn} setGlobalUsername={setUsername}/>}
        />
      </Routes>
    </Router>
  );
};

export default App;