import React from 'react';
import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Grid,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  Paper,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Save as SaveIcon,
  Storage as StorageIcon
} from '@mui/icons-material';
import SectionHeader from './SectionHeader';

const IpSourcesSection = ({
  loading,
  sourceTypes,
  ipsBySource,
  selectedSource,
  newSourceName,
  setNewSourceName,
  newIpAddress,
  setNewIpAddress,
  onAddSourceType,
  onSelectSourceType,
  onAddIp,
  onDeleteIp,
  onSubmitChanges
}) => (
  <Card>
    <CardContent>
      <SectionHeader icon={StorageIcon} title="IP Sources" />

      <Grid container spacing={3}>
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2, backgroundColor: 'background.default' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
              Source Groups
            </Typography>

            <Stack spacing={1.5}>
              <TextField
                size="small"
                label="New Source Name"
                value={newSourceName}
                onChange={(event) => setNewSourceName(event.target.value)}
              />
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={onAddSourceType}
                disabled={!newSourceName.trim()}
              >
                Add Source
              </Button>
            </Stack>

            <Divider sx={{ my: 2 }} />

            {sourceTypes.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                No sources yet.
              </Typography>
            ) : (
              <List dense sx={{ maxHeight: 260, overflow: 'auto' }}>
                {sourceTypes.map((source) => (
                  <ListItemButton
                    key={source}
                    selected={selectedSource === source}
                    onClick={() => onSelectSourceType(source)}
                    sx={{ borderRadius: 1 }}
                  >
                    <ListItemText primary={source} />
                  </ListItemButton>
                ))}
              </List>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2, backgroundColor: 'background.default' }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
              IP Addresses
            </Typography>

            {!selectedSource ? (
              <Typography variant="body2" color="text.secondary">
                Select a source group to manage IPs.
              </Typography>
            ) : (
              <>
                <Box display="flex" gap={1} mb={2}>
                  <TextField
                    size="small"
                    label="Add IP Address"
                    value={newIpAddress}
                    onChange={(event) => setNewIpAddress(event.target.value)}
                    fullWidth
                  />
                  <Button
                    variant="contained"
                    startIcon={<AddIcon />}
                    onClick={onAddIp}
                  >
                    Add
                  </Button>
                </Box>

                <Box sx={{ maxHeight: 240, overflow: 'auto' }}>
                  {(ipsBySource[selectedSource] || []).length === 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      No IPs for this source yet.
                    </Typography>
                  ) : (
                    <List dense>
                      {(ipsBySource[selectedSource] || []).map((ip) => (
                        <ListItem
                          key={ip}
                          secondaryAction={
                            <IconButton
                              edge="end"
                              color="error"
                              onClick={() => onDeleteIp(ip)}
                              size="small"
                            >
                              <DeleteIcon />
                            </IconButton>
                          }
                        >
                          <ListItemText primary={ip} />
                        </ListItem>
                      ))}
                    </List>
                  )}
                </Box>

                <Divider sx={{ my: 2 }} />

                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={onSubmitChanges}
                  disabled={loading}
                  fullWidth
                >
                  Submit Changes
                </Button>
              </>
            )}
          </Paper>
        </Grid>
      </Grid>
    </CardContent>
  </Card>
);

export default IpSourcesSection;
