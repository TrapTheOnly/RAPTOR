import React from 'react';
import { Box, Card, CardContent, Divider, Stack, Typography } from '@mui/material';

const SectionCard = ({
  icon: Icon,
  title,
  description,
  actions,
  children,
  footer,
  disablePadding = false
}) => (
  <Card variant="outlined">
    <CardContent sx={disablePadding ? { p: 0, '&:last-child': { pb: 0 } } : undefined}>
      {(title || actions) && (
        <Box
          display="flex"
          justifyContent="space-between"
          alignItems={{ xs: 'flex-start', sm: 'center' }}
          flexDirection={{ xs: 'column', sm: 'row' }}
          gap={1.5}
          sx={disablePadding ? { px: 2, pt: 2, pb: 1 } : { mb: description ? 0.5 : 2 }}
        >
          <Box display="flex" alignItems="center" sx={{ minWidth: 0 }}>
            {Icon && <Icon sx={{ color: 'primary.main', mr: 1, fontSize: 20 }} />}
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              {title}
            </Typography>
          </Box>
          {actions && (
            <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
              {actions}
            </Stack>
          )}
        </Box>
      )}
      {description && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={disablePadding ? { px: 2, pb: 1.5 } : { mb: 2 }}
        >
          {description}
        </Typography>
      )}
      {children}
      {footer && (
        <>
          <Divider sx={{ my: 1.5 }} />
          {footer}
        </>
      )}
    </CardContent>
  </Card>
);

export default SectionCard;
