import React from 'react';
import { Box, Typography, Button, ThemeProvider, createTheme, CssBaseline } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom'; // Import Link from react-router-dom
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

const ErrorPage = ({ errorCode, errorMessage, darkMode }) => { // Accept props

  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: darkMode ? '#90caf9' : '#1976d2',
      },
      secondary: {
        main: darkMode ? '#f48fb1' : '#d81b60',
      },
    },
  });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline/>
    <Box
      display="flex"
      flexDirection="column"
      justifyContent="center"
      alignItems="center"
      minHeight="100vh"
      bgcolor={theme.palette.background.default}
      p={3}
    >
      <ErrorOutlineIcon sx={{ fontSize: 80, color: theme.palette.error.main, mb: 2 }} />
      <Typography variant="h1" component="h1" gutterBottom color="error">
        Error {errorCode}
      </Typography>
      <Typography variant="h5" component="h2" gutterBottom>
        {errorMessage}
      </Typography>

      {errorCode === 404 && (
        <Typography variant="body1" paragraph>
          Oops! It looks like you've wandered into uncharted territory. This page doesn't exist.
           <br/> <img src="https://http.cat/404" alt="404 Cat" style={{maxWidth: "100%", height: "auto"}}/>
        </Typography>

      )}
        {errorCode === 401 && (
        <Typography variant="body1" paragraph>
          Hold on there! You need to be logged in to access this page.
        </Typography>
      )}

      {errorCode === 403 && (
        <Typography variant="body1" paragraph>
        You shall not pass! You don't have permission to access this resource.
        </Typography>
      )}

      <Button
        variant="contained"
        color="primary"
        component={RouterLink} // Use RouterLink
        to="/" // Link to the homepage
        sx={{ mt: 2 }}
      >
        Go to Homepage
      </Button>
    </Box>
    </ThemeProvider>
  );
};

export default ErrorPage;