import React from 'react';
import { Box, Checkbox, FormControlLabel, Paper, Typography } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import { OPTIONAL_PERMISSION_LABELS } from '../constants';
import { getOptionalPermissions } from '../utils';

const OptionalPermissionControls = ({ roleKey, permissions, onToggle }) => {
  const theme = useTheme();
  const optionalPermissions = getOptionalPermissions(roleKey);

  return (
    <Paper
      sx={{
        mt: 1.5,
        p: 1.5,
        borderRadius: 2,
        border: `1px solid ${alpha(theme.palette.primary.main, 0.15)}`,
        background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.06)} 0%, ${alpha(theme.palette.secondary.main, 0.05)} 100%)`
      }}
    >
      <Typography
        variant="caption"
        sx={{ display: 'block', fontWeight: 700, letterSpacing: 0.6, textTransform: 'uppercase', color: 'text.secondary' }}
      >
        Optional permissions
      </Typography>
      {optionalPermissions.length === 0 ? (
        <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
          No optional permissions for this role.
        </Typography>
      ) : (
        <Box sx={{ mt: 1, display: 'grid', gap: 0.75 }}>
          {optionalPermissions.map((permission) => {
            const meta = OPTIONAL_PERMISSION_LABELS[permission] || { label: permission, description: '' };
            const isChecked = permissions.includes(permission);
            return (
              <Box
                key={permission}
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 0.35,
                  p: 0.75,
                  borderRadius: 1.5,
                  border: `1px solid ${alpha(theme.palette.divider, 0.4)}`,
                  backgroundColor: isChecked ? alpha(theme.palette.primary.main, 0.12) : alpha(theme.palette.background.paper, 0.6),
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    borderColor: alpha(theme.palette.primary.main, 0.4),
                    transform: 'translateY(-1px)'
                  }
                }}
              >
                <FormControlLabel
                  sx={{ m: 0 }}
                  control={
                    <Checkbox
                      size="small"
                      checked={isChecked}
                      onChange={() => onToggle(permission)}
                      sx={{
                        color: alpha(theme.palette.primary.main, 0.6),
                        '&.Mui-checked': { color: theme.palette.primary.main }
                      }}
                    />
                  }
                  label={
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {meta.label}
                    </Typography>
                  }
                />
                {meta.description && (
                  <Typography variant="caption" color="text.secondary" sx={{ ml: 3.5 }}>
                    {meta.description}
                  </Typography>
                )}
              </Box>
            );
          })}
        </Box>
      )}
    </Paper>
  );
};

export default OptionalPermissionControls;
