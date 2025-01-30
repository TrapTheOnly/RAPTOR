import React from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AppBar, Toolbar, Button, Typography, Box, Switch } from '@mui/material';
import LightModeIcon from '@mui/icons-material/LightMode';
import DarkModeIcon from '@mui/icons-material/DarkMode';

const Header = ({ username, userRole, setUserRole, setLoggedIn, setUsername, darkMode, setDarkMode }) => {
  const navigate = useNavigate();
  const appBarColor = userRole === "admin" ? "error" : "primary";

  const handleLogout = async () => {
    try {
      await axios.post(`/logout`);
      navigate('/login'); 
      setLoggedIn(false); 
      setUsername('');
      setUserRole(null);
    } catch (error) {}
  };

  return (
    <AppBar position="static" color={appBarColor}>
      <Toolbar>
        <Typography variant="h6" style={{ flexGrow: 1, cursor: 'pointer' }} onClick={() => navigate('/')}>
          ADAM
        </Typography>
        <Box display="flex" alignItems="center">
          <Typography variant="body1" style={{ marginRight: '1rem' }}>
            Hello, {username}
          </Typography>
          <LightModeIcon />
          <Switch
            checked={darkMode}
            onChange={() => setDarkMode(!darkMode)}
            sx={{
              '& .MuiSwitch-thumb': {
                backgroundColor: darkMode ? 'warning.main' : 'white',
              },
              '& .MuiSwitch-track': {
                backgroundColor: darkMode ? '#fdd835' : '#e0e0e0',
              },
            }}
          />
          <DarkModeIcon />
          {userRole === "admin" && (
            <Button color="inherit" onClick={() => navigate('/settings')}>
              Settings
            </Button>
          )}
          <Button color="inherit" onClick={handleLogout}>
            Logout
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;