import React from 'react';
import { Box, Card, CardContent, Chip, Stack, Typography } from '@mui/material';

const TesterWorkloadCard = ({ rows }) => (
  <Card variant="outlined" sx={{ height: '100%' }}>
    <CardContent>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        Tester Workload
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
        Assignment health by tester with in-progress and open-risk focus.
      </Typography>

      {rows.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No tester activity available.
        </Typography>
      ) : (
        <Stack spacing={1.1}>
          {rows.map((row) => (
            <Box
              key={row.tester}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                p: 1.15
              }}
            >
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems={{ xs: 'flex-start', sm: 'center' }}
                flexDirection={{ xs: 'column', sm: 'row' }}
                gap={0.75}
              >
                <Typography variant="body2" sx={{ fontWeight: 700 }}>
                  {row.tester}
                </Typography>
                <Stack direction="row" spacing={0.6} useFlexGap flexWrap="wrap">
                  <Chip size="small" label={`Total ${row.total}`} variant="outlined" />
                  <Chip size="small" color="primary" label={`In Progress ${row.inProgress}`} />
                  <Chip
                    size="small"
                    color={row.openRiskAssets > 0 ? 'error' : 'success'}
                    label={`Open Risk ${row.openRiskAssets}`}
                  />
                </Stack>
              </Box>
            </Box>
          ))}
        </Stack>
      )}
    </CardContent>
  </Card>
);

export default TesterWorkloadCard;
