import React from 'react';
import { Box, Chip, Grid, Paper, Typography } from '@mui/material';
import {
  CheckCircle,
  Computer,
  FilterList,
  Update,
  Warning
} from '@mui/icons-material';

const RecordsStatsBar = ({ stats, filteredCount, activeFilterCount }) => (
  <Paper sx={{ p: 2, mb: 3, backgroundColor: 'background.paper' }}>
    <Grid container spacing={3} alignItems="center">
      <Grid item>
        <Box display="flex" alignItems="center">
          <Computer sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="h6" sx={{ mr: 1 }}>
            {stats.total}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Total
          </Typography>
        </Box>
      </Grid>
      <Grid item>
        <Box display="flex" alignItems="center">
          <CheckCircle sx={{ mr: 1, color: '#4CAF50' }} />
          <Typography variant="h6" sx={{ mr: 1 }}>
            {stats.active}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Active
          </Typography>
        </Box>
      </Grid>
      <Grid item>
        <Box display="flex" alignItems="center">
          <Update sx={{ mr: 1, color: '#2196F3' }} />
          <Typography variant="h6" sx={{ mr: 1 }}>
            {stats.updated}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Updated
          </Typography>
        </Box>
      </Grid>
      <Grid item>
        <Box display="flex" alignItems="center">
          <Warning sx={{ mr: 1, color: '#FF9800' }} />
          <Typography variant="h6" sx={{ mr: 1 }}>
            {stats.missing}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Issues
          </Typography>
        </Box>
      </Grid>
      <Grid item>
        <Box display="flex" alignItems="center">
          <FilterList sx={{ mr: 1, color: 'text.secondary' }} />
          <Typography variant="h6" sx={{ mr: 1 }}>
            {stats.sources}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Sources
          </Typography>
        </Box>
      </Grid>
      <Grid item xs />
      <Grid item>
        <Typography variant="body2" color="text.secondary">
          Showing {filteredCount} of {stats.total} records
          {activeFilterCount > 0 && (
            <Chip
              label={`${activeFilterCount} filter${activeFilterCount !== 1 ? 's' : ''}`}
              size="small"
              sx={{ ml: 1, height: 20 }}
            />
          )}
        </Typography>
      </Grid>
    </Grid>
  </Paper>
);

export default RecordsStatsBar;
