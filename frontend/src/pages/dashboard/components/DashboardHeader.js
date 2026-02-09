import React from 'react';
import { Box, Button, Chip, Stack, Typography } from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';

const DashboardHeader = ({ generatedAt, onRefresh, loading }) => (
  <Box
    display="flex"
    justifyContent="space-between"
    alignItems={{ xs: 'flex-start', md: 'center' }}
    flexDirection={{ xs: 'column', md: 'row' }}
    gap={2}
    mb={3}
  >
    <Box>
      <Typography variant="h4" sx={{ fontWeight: 700 }}>
        Security Operations Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
        Manager-focused overview of testing velocity, exposure, and recent security events.
      </Typography>
    </Box>

    <Stack direction="row" spacing={1} alignItems="center">
      <Chip
        size="small"
        variant="outlined"
        label={`Updated ${new Date(generatedAt).toLocaleTimeString([], {
          hour: '2-digit',
          minute: '2-digit'
        })}`}
      />
      <Button
        variant="outlined"
        size="small"
        startIcon={<RefreshIcon />}
        onClick={onRefresh}
        disabled={loading}
      >
        Refresh
      </Button>
    </Stack>
  </Box>
);

export default DashboardHeader;
