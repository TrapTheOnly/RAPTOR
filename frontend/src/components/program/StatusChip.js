import React from 'react';
import { Chip } from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import { severityConfig, statusMeta } from '../../theme/tokens';

const Tinted = ({ color, label, size = 'small', variant, ...rest }) => (
  <Chip
    size={size}
    label={label}
    variant={variant}
    sx={{
      backgroundColor: variant === 'outlined' ? 'transparent' : alpha(color, 0.14),
      borderColor: alpha(color, 0.4),
      color,
      fontWeight: 600,
      fontSize: '0.75rem'
    }}
    {...rest}
  />
);

export const StatusChip = ({ status, label, ...rest }) => {
  const { palette } = useTheme();
  const meta = statusMeta(status, palette.mode);
  return <Tinted color={meta.color} label={label || meta.label} {...rest} />;
};

export const SeverityChip = ({ score, showScore = true, ...rest }) => {
  const { palette } = useTheme();
  const meta = severityConfig(score, palette.mode);
  const numeric = Number(score || 0);
  const label = showScore && numeric > 0 ? `${meta.label} ${numeric.toFixed(1)}` : meta.label;
  return <Tinted color={meta.color} label={label} {...rest} />;
};

export const CountChip = ({ color, label, ...rest }) => (
  <Tinted color={color} label={label} {...rest} />
);

export default StatusChip;
