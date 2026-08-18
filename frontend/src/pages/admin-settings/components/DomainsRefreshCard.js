import React from 'react';
import { Box, Button, Card, CardContent, Typography } from '@mui/material';
import { Refresh as RefreshIcon } from '@mui/icons-material';

const DomainsRefreshCard = ({ loading, onRunUpdate }) => (
  <Card>
    <CardContent
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 2,
        '&:last-child': { pb: 2 }
      }}
    >
      <Box flex={1} minWidth={240}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Refresh
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Parse RAPTOR drop-folder files (<code>*_A_Records</code>) and ask every enrolled
          collector to collect now. Agents parse BIND, PowerDNS, or Windows DNS locally and POST
          records; they do not copy zone files. Two-sided agents collect immediately if reachable;
          one-sided agents collect on their next heartbeat.
        </Typography>
      </Box>
      <Button
        variant="contained"
        startIcon={<RefreshIcon />}
        onClick={onRunUpdate}
        disabled={loading}
        sx={{ flexShrink: 0 }}
      >
        Run update
      </Button>
    </CardContent>
  </Card>
);

export default DomainsRefreshCard;
