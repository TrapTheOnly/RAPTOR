import React from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  IconButton,
  List,
  ListItem,
  ListItemText,
  TextField,
  Typography
} from '@mui/material';
import {
  Add as AddIcon,
  BugReport as BugReportIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';
import SectionHeader from './SectionHeader';

const VulnCategoriesSection = ({
  loading,
  vulnCategories,
  newCategoryName,
  setNewCategoryName,
  onAddVulnCategory,
  onDeleteVulnCategory
}) => (
  <Card>
    <CardContent>
      <SectionHeader icon={BugReportIcon} title="Vulnerability Categories" />

      <Box display="flex" gap={1} mb={2}>
        <TextField
          fullWidth
          size="small"
          placeholder="Add new category"
          value={newCategoryName}
          onChange={(event) => setNewCategoryName(event.target.value)}
        />
        <Button
          variant="contained"
          size="small"
          startIcon={<AddIcon />}
          onClick={onAddVulnCategory}
          disabled={loading}
        >
          Add
        </Button>
      </Box>

      {vulnCategories.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No categories found.
        </Typography>
      ) : (
        <List sx={{ maxHeight: 300, overflow: 'auto' }}>
          {vulnCategories.map((category) => (
            <ListItem
              key={category.id}
              secondaryAction={
                <IconButton
                  edge="end"
                  color="error"
                  onClick={() => onDeleteVulnCategory(category.id)}
                  size="small"
                >
                  <DeleteIcon />
                </IconButton>
              }
            >
              <ListItemText
                primary={category.name}
                secondary={category.is_custom ? 'Custom' : 'Default'}
              />
            </ListItem>
          ))}
        </List>
      )}
    </CardContent>
  </Card>
);

export default VulnCategoriesSection;
