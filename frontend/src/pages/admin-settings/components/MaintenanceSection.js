import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Stack,
  Typography
} from '@mui/material';
import {
  Download as DownloadIcon,
  Warning as WarningIcon
} from '@mui/icons-material';

const MaintenanceSection = ({
  loading,
  resetCsv,
  resetStats,
  onDownloadResetCsv,
  onOpenResetDialog
}) => (
  <Stack spacing={3}>
    <Card>
      <CardContent>
        <Box display="flex" alignItems="center" mb={2}>
          <WarningIcon sx={{ color: 'warning.main', mr: 1 }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            Pentest Reset
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Reset pentest progress for all records except open vulnerabilities.
        </Typography>

        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center">
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={onDownloadResetCsv}
            disabled={!resetCsv}
          >
            Download Summary CSV
          </Button>
          <Button
            variant="contained"
            color="warning"
            startIcon={<WarningIcon />}
            onClick={onOpenResetDialog}
          >
            Reset Pentest Progress
          </Button>
        </Stack>

        {resetStats && (
          <Alert severity="info" sx={{ mt: 2 }}>
            Reset completed. {resetStats.total_reset} records cleared, {resetStats.remaining_open} open
            vulnerabilities preserved.
          </Alert>
        )}
      </CardContent>
    </Card>
  </Stack>
);

export default MaintenanceSection;
