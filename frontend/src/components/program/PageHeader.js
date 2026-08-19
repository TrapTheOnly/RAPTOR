import React from 'react';
import { Box, Breadcrumbs, Link, Stack, Typography } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { NavigateNext } from '@mui/icons-material';

const PageHeader = ({ title, subtitle, crumbs = [], actions, meta }) => (
  <Box sx={{ mb: 3 }}>
    {crumbs.length > 0 && (
      <Breadcrumbs
        separator={<NavigateNext fontSize="small" />}
        sx={{ mb: 1, '& .MuiBreadcrumbs-li': { display: 'flex', alignItems: 'center' } }}
      >
        {crumbs.map((crumb) =>
          crumb.to ? (
            <Link
              key={crumb.label}
              component={RouterLink}
              to={crumb.to}
              underline="hover"
              color="text.secondary"
              variant="body2"
            >
              {crumb.label}
            </Link>
          ) : (
            <Typography key={crumb.label} variant="body2" color="text.primary" sx={{ fontWeight: 600 }}>
              {crumb.label}
            </Typography>
          )
        )}
      </Breadcrumbs>
    )}
    <Box
      display="flex"
      justifyContent="space-between"
      alignItems={{ xs: 'flex-start', md: 'center' }}
      flexDirection={{ xs: 'column', md: 'row' }}
      gap={2}
    >
      <Box sx={{ minWidth: 0 }}>
        <Stack direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {title}
          </Typography>
          {meta}
        </Stack>
        {subtitle && (
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            {subtitle}
          </Typography>
        )}
      </Box>
      {actions && (
        <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
          {actions}
        </Stack>
      )}
    </Box>
  </Box>
);

export default PageHeader;
