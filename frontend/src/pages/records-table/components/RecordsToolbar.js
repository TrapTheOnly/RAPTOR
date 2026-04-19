import React from 'react';
import { alpha, Box, Button, FormControlLabel, Stack, Switch } from '@mui/material';
import { AccountTree, Add } from '@mui/icons-material';

const RecordsToolbar = ({
  groupByApp,
  onToggleGroupByApp,
  canManageApps,
  canCreateManualRecords,
  onOpenCreateDialog,
  onOpenAppsDialog,
  theme
}) => (
  <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
    <FormControlLabel
      control={
        <Switch
          checked={groupByApp}
          onChange={(event) => onToggleGroupByApp(event.target.checked)}
          color="primary"
        />
      }
      label="Group by application"
    />
    <Stack direction="row" spacing={1}>
      {canCreateManualRecords && (
        <Button
          variant="contained"
          size="small"
          startIcon={<Add />}
          onClick={onOpenCreateDialog}
        >
          Add Manual Domain
        </Button>
      )}
      {canManageApps && (
        <Button
          variant="outlined"
          size="small"
          startIcon={<AccountTree />}
          onClick={onOpenAppsDialog}
          sx={{
            borderColor: alpha(theme.palette.primary.main, 0.4),
            color: theme.palette.primary.main,
            backgroundColor: alpha(theme.palette.primary.main, 0.08),
            transition: 'all 0.2s ease',
            '&:hover': {
              backgroundColor: alpha(theme.palette.primary.main, 0.15),
              borderColor: theme.palette.primary.main,
              transform: 'translateY(-1px)'
            }
          }}
        >
          Manage Apps
        </Button>
      )}
    </Stack>
  </Box>
);

export default RecordsToolbar;
