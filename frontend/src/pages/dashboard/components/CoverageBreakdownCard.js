import React from 'react';
import { Box, Card, CardContent, LinearProgress, Stack, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';

const MetricRow = ({ label, value, progress, color }) => (
  <Box>
    <Box display="flex" justifyContent="space-between" alignItems="center" mb={0.5}>
      <Typography variant="body2">{label}</Typography>
      <Typography variant="body2" sx={{ fontWeight: 700 }}>
        {value}
      </Typography>
    </Box>
    <LinearProgress
      variant="determinate"
      value={Math.max(0, Math.min(100, progress))}
      sx={{
        height: 8,
        borderRadius: 999,
        backgroundColor: alpha(color, 0.15),
        '& .MuiLinearProgress-bar': {
          backgroundColor: color
        }
      }}
    />
  </Box>
);

const CoverageBreakdownCard = ({ kpis }) => (
  <Card variant="outlined" sx={{ height: '100%' }}>
    <CardContent>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        Execution Health
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
        Coverage and remediation performance at a glance.
      </Typography>

      <Stack spacing={1.5}>
        <MetricRow
          label="Coverage"
          value={`${kpis.startedTests}/${kpis.totalAssets}`}
          progress={kpis.coveragePct}
          color="#00897b"
        />
        <MetricRow
          label="Fix Rate"
          value={`${kpis.fixRatePct}%`}
          progress={kpis.fixRatePct}
          color="#2e7d32"
        />
        <MetricRow
          label="In Progress Ratio"
          value={`${kpis.inProgressTests}/${kpis.totalAssets}`}
          progress={kpis.totalAssets > 0 ? (kpis.inProgressTests / kpis.totalAssets) * 100 : 0}
          color="#1976d2"
        />
      </Stack>
    </CardContent>
  </Card>
);

export default CoverageBreakdownCard;
