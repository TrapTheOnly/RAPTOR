import React from 'react';
import { Box, Collapse, ListItemButton, ListItemText, Paper } from '@mui/material';
import { ExpandLess, ExpandMore, Folder, FolderOpen } from '@mui/icons-material';

const AppGroupsList = ({ groups, expandedApps, onToggleAppGroup, renderRecordCard, theme }) => {
  if (groups.length === 0) {
    return null;
  }

  return groups.map((group) => (
    <Paper
      key={group.key}
      sx={{
        mb: 2,
        border: `1px solid ${theme.palette.divider}`,
        backgroundColor: 'background.paper'
      }}
    >
      <ListItemButton onClick={() => onToggleAppGroup(group.key)}>
        <Box display="flex" alignItems="center" flex={1} gap={1.5}>
          {expandedApps.has(group.key) ? (
            <FolderOpen sx={{ color: theme.palette.primary.main }} />
          ) : (
            <Folder sx={{ color: theme.palette.primary.main }} />
          )}
          <ListItemText
            primary={group.name}
            secondary={`${group.records.length} domain${group.records.length === 1 ? '' : 's'}`}
            primaryTypographyProps={{ fontWeight: 600 }}
          />
        </Box>
        {expandedApps.has(group.key) ? <ExpandLess /> : <ExpandMore />}
      </ListItemButton>
      <Collapse in={expandedApps.has(group.key)} timeout="auto" unmountOnExit>
        <Box sx={{ p: 1 }}>{group.records.map(renderRecordCard)}</Box>
      </Collapse>
    </Paper>
  ));
};

export default AppGroupsList;
