import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { Page } from '../design/primitives';

const Error = ({ errorCode, errorMessage }) => (
  <Page>
    <Box
      display="flex"
      flexDirection="column"
      justifyContent="center"
      alignItems="center"
      minHeight="70vh"
    >
      <ErrorOutlineIcon color="error" sx={{ fontSize: 48, mb: 2 }} />
      <Typography variant="h1" component="h1" gutterBottom>
        Error {errorCode}
      </Typography>
      <Typography variant="h5" component="h2" gutterBottom>
        {errorMessage}
      </Typography>
      {errorCode === 404 && (
        <Typography variant="body1" color="text.secondary" paragraph>
          This page does not exist.
        </Typography>
      )}
      {errorCode === 401 && (
        <Typography variant="body1" color="text.secondary" paragraph>
          You need to be logged in to access this page.
        </Typography>
      )}
      {errorCode === 403 && (
        <Typography variant="body1" color="text.secondary" paragraph>
          You do not have permission to access this resource.
        </Typography>
      )}
      <Button variant="contained" component={RouterLink} to="/">
        Go to homepage
      </Button>
    </Box>
  </Page>
);

export default Error;
