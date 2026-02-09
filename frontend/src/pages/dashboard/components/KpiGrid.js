import React from 'react';
import { Box, Card, CardContent, Grid, LinearProgress, Typography } from '@mui/material';
import { alpha } from '@mui/material/styles';

const KpiCard = ({ item }) => (
  <Card variant="outlined" sx={{ height: '100%' }}>
    <CardContent>
      <Box
        sx={{
          display: 'inline-flex',
          px: 1,
          py: 0.25,
          borderRadius: 1,
          fontSize: '0.72rem',
          textTransform: 'uppercase',
          letterSpacing: 0.4,
          fontWeight: 600,
          color: item.color,
          backgroundColor: alpha(item.color, 0.12),
          mb: 1
        }}
      >
        {item.label}
      </Box>
      <Typography variant="h4" sx={{ fontWeight: 700, lineHeight: 1.15 }}>
        {item.value}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
        {item.subtitle}
      </Typography>
      {typeof item.progress === 'number' && (
        <LinearProgress
          variant="determinate"
          value={Math.max(0, Math.min(100, item.progress))}
          sx={{
            mt: 1.5,
            height: 6,
            borderRadius: 999,
            backgroundColor: alpha(item.color, 0.12),
            '& .MuiLinearProgress-bar': {
              backgroundColor: item.color
            }
          }}
        />
      )}
    </CardContent>
  </Card>
);

const KpiGrid = ({ items }) => (
  <Grid container spacing={2} mb={3}>
    {items.map((item) => (
      <Grid item xs={12} sm={6} md={4} lg={3} key={item.key}>
        <KpiCard item={item} />
      </Grid>
    ))}
  </Grid>
);

export default KpiGrid;
