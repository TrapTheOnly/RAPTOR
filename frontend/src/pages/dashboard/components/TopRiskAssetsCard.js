import React from 'react';
import { Box, Card, CardContent, Chip, Stack, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';

const TopRiskAssetsCard = ({ assets }) => (
  <Card variant="outlined" sx={{ height: '100%' }}>
    <CardContent>
      <Typography variant="h6" sx={{ fontWeight: 700 }}>
        Top Risk Assets
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, mb: 2 }}>
        Prioritized by unresolved findings and vulnerability volume.
      </Typography>

      {assets.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No high-risk assets detected.
        </Typography>
      ) : (
        <Stack spacing={1.2}>
          {assets.map((asset) => (
            <Box
              key={asset.key}
              sx={{
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                p: 1.25
              }}
            >
              <Box
                display="flex"
                justifyContent="space-between"
                alignItems={{ xs: 'flex-start', sm: 'center' }}
                flexDirection={{ xs: 'column', sm: 'row' }}
                gap={0.75}
              >
                <Box>
                  <Typography variant="body2" sx={{ fontWeight: 700 }}>
                    {asset.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {asset.source} • {asset.testedBy}
                  </Typography>
                </Box>
                <Stack direction="row" spacing={0.6} useFlexGap flexWrap="wrap">
                  <Chip
                    size="small"
                    label={`${asset.vulnerabilityCount} findings`}
                    sx={{
                      backgroundColor: alpha('#ef6c00', 0.12),
                      color: '#ef6c00',
                      fontWeight: 600
                    }}
                  />
                  <Chip
                    size="small"
                    label={asset.openRisk ? 'Open Risk' : 'Remediated'}
                    color={asset.openRisk ? 'error' : 'success'}
                    variant={asset.openRisk ? 'filled' : 'outlined'}
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

export default TopRiskAssetsCard;
