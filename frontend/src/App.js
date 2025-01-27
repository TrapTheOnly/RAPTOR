import React, { useState } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import Login from './components/Login';
import RecordsTable from './components/RecordsTable';

const App = () => {
  const [loggedIn, setLoggedIn] = useState(false);

  return (
    <Router>
      <Routes>
        <Route
          path="/"
          element={loggedIn ? <RecordsTable /> : <Navigate to="/login" />}
        />
        <Route
          path="/login"
          element={<Login setLoggedIn={setLoggedIn} />}
        />
      </Routes>
    </Router>
  );
};

export default App;