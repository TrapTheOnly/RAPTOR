import React from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { AppBar, Toolbar, Button, Typography, Box } from '@mui/material';

const Header = ({ username, setLoggedIn, setUsername }) => {
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await axios.post(`/logout`);
      navigate('/login'); 
      setLoggedIn(false); 
      setUsername(''); 
    } catch (error) {
      console.error("Error logging out:", error);
    }
  };

  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" style={{ flexGrow: 1 }}>
          DNS Monitoring
        </Typography>
        <Box display="flex" alignItems="center">
          <Typography variant="body1" style={{ marginRight: '1rem' }}>
            Hello, {username || 'User'}
          </Typography>
          <Button color="inherit" onClick={handleLogout}>
            Logout
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Header;