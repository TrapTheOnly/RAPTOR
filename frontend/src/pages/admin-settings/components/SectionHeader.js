import React from 'react';
import { Box, Typography } from '@mui/material';

const SectionHeader = ({ icon: Icon, title, children, marginBottom = 3 }) => (
  <Box display="flex" alignItems="center" mb={marginBottom}>
    <Icon sx={{ color: 'primary.main', mr: 1 }} />
    <Typography variant="h6" sx={{ fontWeight: 600 }}>
      {title}
    </Typography>
    {children}
  </Box>
);

export default SectionHeader;
