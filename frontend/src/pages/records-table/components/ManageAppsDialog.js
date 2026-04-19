import React from 'react';
import {
  alpha,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItemButton,
  Paper,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import { AccountTree, Delete, Save } from '@mui/icons-material';

const ManageAppsDialog = ({
  open,
  onClose,
  apps,
  newAppName,
  onSetNewAppName,
  appEdits,
  onSetAppEdits,
  appsBusy,
  onCreateApp,
  onRenameApp,
  onDeleteApp,
  theme
}) => {
  const appDialogIconBg = alpha(
    theme.palette.primary.main,
    theme.palette.mode === 'dark' ? 0.22 : 0.14
  );
  const appDialogIconColor =
    theme.palette.mode === 'dark' ? theme.palette.primary.light : theme.palette.primary.dark;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          overflow: 'hidden',
          backgroundColor: theme.palette.background.paper,
          border: `1px solid ${alpha(theme.palette.divider, 0.8)}`,
          boxShadow: theme.shadows[12]
        }
      }}
    >
      <DialogTitle sx={{ pb: 2, borderBottom: `1px solid ${theme.palette.divider}` }}>
        <Box display="flex" alignItems="center" gap={1.5}>
          <Box
            sx={{
              width: 40,
              height: 40,
              borderRadius: 2,
              backgroundColor: appDialogIconBg,
              border: `1px solid ${alpha(theme.palette.primary.main, 0.35)}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              lineHeight: 0
            }}
          >
            <AccountTree sx={{ color: appDialogIconColor, fontSize: 22 }} />
          </Box>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              Manage Applications
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Group domains into apps for a cleaner records tree.
            </Typography>
          </Box>
        </Box>
      </DialogTitle>
      <DialogContent sx={{ pt: 2.5 }}>
        <br></br>
        <Paper
          sx={{
            p: 2,
            mb: 2,
            borderRadius: 2,
            border: `1px solid ${alpha(theme.palette.primary.main, 0.12)}`,
            backgroundColor: 'background.paper'
          }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
            Create a new application
          </Typography>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <TextField
              fullWidth
              label="New application"
              value={newAppName}
              onChange={(event) => onSetNewAppName(event.target.value)}
              size="small"
              sx={{ backgroundColor: 'background.default' }}
            />
            <Button
              variant="contained"
              onClick={onCreateApp}
              disabled={!newAppName.trim() || appsBusy}
              sx={{
                px: 3,
                boxShadow: '0 8px 16px rgba(0,0,0,0.12)',
                transition: 'all 0.2s ease',
                '&:hover': {
                  transform: 'translateY(-1px)',
                  boxShadow: '0 12px 20px rgba(0,0,0,0.16)'
                }
              }}
            >
              Create
            </Button>
          </Stack>
        </Paper>

        <Paper
          sx={{
            p: 2,
            borderRadius: 2,
            border: `1px solid ${alpha(theme.palette.divider, 0.6)}`,
            backgroundColor: 'background.paper'
          }}
        >
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1.5 }}>
            Existing applications
          </Typography>
          {apps.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No applications created yet.
            </Typography>
          ) : (
            <List sx={{ p: 0, display: 'grid', gap: 1 }}>
              {apps.map((app) => (
                <ListItemButton
                  key={app.id}
                  sx={{
                    px: 1,
                    py: 1,
                    borderRadius: 1.5,
                    border: `1px solid ${alpha(theme.palette.divider, 0.5)}`,
                    backgroundColor: alpha(theme.palette.background.default, 0.8),
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      backgroundColor: alpha(theme.palette.primary.main, 0.08),
                      borderColor: alpha(theme.palette.primary.main, 0.3)
                    }
                  }}
                >
                  <Box display="flex" alignItems="center" gap={1} width="100%">
                    <TextField
                      fullWidth
                      size="small"
                      value={appEdits[app.id] ?? app.name}
                      onChange={(event) =>
                        onSetAppEdits((prev) => ({ ...prev, [app.id]: event.target.value }))
                      }
                      sx={{ backgroundColor: 'background.paper' }}
                    />
                    <IconButton
                      onClick={() => onRenameApp(app.id)}
                      disabled={appsBusy}
                      size="small"
                      color="primary"
                      sx={{
                        backgroundColor: alpha(theme.palette.primary.main, 0.12),
                        '&:hover': { backgroundColor: alpha(theme.palette.primary.main, 0.2) }
                      }}
                    >
                      <Save />
                    </IconButton>
                    <IconButton
                      onClick={() => onDeleteApp(app.id)}
                      disabled={appsBusy}
                      size="small"
                      color="error"
                      sx={{
                        backgroundColor: alpha(theme.palette.error.main, 0.12),
                        '&:hover': { backgroundColor: alpha(theme.palette.error.main, 0.2) }
                      }}
                    >
                      <Delete />
                    </IconButton>
                  </Box>
                </ListItemButton>
              ))}
            </List>
          )}
        </Paper>

        <Typography variant="caption" color="text.secondary" sx={{ mt: 2, display: 'block' }}>
          Assign domains by editing a record and selecting an application.
        </Typography>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} variant="outlined">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ManageAppsDialog;
