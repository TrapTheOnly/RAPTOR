import React from 'react';
import { Box, Card, CardContent, Stack, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';
import {
  CheckCircleOutline as CheckCircleOutlineIcon,
  ErrorOutline as ErrorOutlineIcon,
  PlayCircleOutline as PlayCircleOutlineIcon,
  SyncAlt as SyncAltIcon,
  WarningAmber as WarningAmberIcon
} from '@mui/icons-material';
import { formatActivityTimestamp } from '../utils';

const ACTIVITY_META = {
  test_started: {
    icon: PlayCircleOutlineIcon,
    color: '#0288d1'
  },
  test_completed: {
    icon: CheckCircleOutlineIcon,
    color: '#2e7d32'
  },
  vuln_detected: {
    icon: WarningAmberIcon,
    color: '#ef6c00'
  },
  scope_updated: {
    icon: SyncAltIcon,
    color: '#5e35b1'
  },
  scope_missing: {
    icon: ErrorOutlineIcon,
    color: '#d32f2f'
  }
};

const RecentActivityCard = ({ events }) => (
  <Card variant="outlined" sx={{ height: '100%' }}>
    <CardContent>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        Recent Changes
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
        Includes recently started tests, newly detected vulnerabilities, and scope updates.
      </Typography>

      {events.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No recent changes in the last 30 days.
        </Typography>
      ) : (
        <Stack spacing={1.25}>
          {events.map((event) => {
            const meta = ACTIVITY_META[event.type] || ACTIVITY_META.scope_updated;
            const Icon = meta.icon;
            return (
              <Box key={event.id} display="flex" alignItems="center" gap={1.25}>
                <Box
                  sx={{
                    width: 30,
                    height: 30,
                    borderRadius: '50%',
                    backgroundColor: alpha(meta.color, 0.12),
                    color: meta.color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0
                  }}
                >
                  <Icon sx={{ fontSize: 18 }} />
                </Box>
                <Box flex={1} minWidth={0}>
                  <Typography variant="body2" sx={{ fontWeight: 600, lineHeight: 1.2 }}>
                    {event.title}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" noWrap>
                    {event.subtitle}
                  </Typography>
                </Box>
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ whiteSpace: 'nowrap' }}
                >
                  {formatActivityTimestamp(event.timestamp)}
                </Typography>
              </Box>
            );
          })}
        </Stack>
      )}
    </CardContent>
  </Card>
);

export default RecentActivityCard;
