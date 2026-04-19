import React from 'react';
import { Chip } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';

const AuthTypeChip = ({ authType }) => {
  const theme = useTheme();
  const normalized = (authType || 'ldap').toLowerCase();
  const configs = {
    local: { label: 'Local', color: theme.palette.warning.main },
    ldap: { label: 'LDAP', color: theme.palette.info.main },
    service: { label: 'Service', color: theme.palette.success.main }
  };
  const config = configs[normalized] || configs.ldap;

  return (
    <Chip
      label={config.label}
      size="small"
      sx={{
        backgroundColor: alpha(config.color, 0.1),
        color: config.color,
        fontWeight: 600
      }}
    />
  );
};

export default AuthTypeChip;
