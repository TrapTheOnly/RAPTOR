import React from 'react';
import {
  alpha,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Collapse,
  Divider,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import {
  Cancel,
  Delete,
  Edit,
  ExpandLess,
  ExpandMore,
  History,
  SyncProblem,
  Save,
  Security
} from '@mui/icons-material';
import { SOURCE_COLORS } from '../constants';
import { formatDateTime } from '../utils';

const getStatusChip = (status, theme) => {
  const configs = {
    unchanged: { label: 'Active', color: '#4CAF50' },
    updated: { label: 'Updated', color: '#2196F3' },
    missing: { label: 'Missing', color: '#FF9800' }
  };

  const config = configs[status] || { label: 'Unknown', color: theme.palette.text.secondary };

  return (
    <Chip
      size="small"
      label={config.label}
      sx={{
        backgroundColor: alpha(config.color, 0.1),
        color: config.color,
        fontWeight: 500,
        fontSize: '0.75rem'
      }}
    />
  );
};

const getSourceAvatar = (source) => (
  <Avatar
    sx={{
      width: 24,
      height: 24,
      fontSize: '0.75rem',
      backgroundColor: SOURCE_COLORS[source] || SOURCE_COLORS.Other,
      mr: 1
    }}
  >
    {source?.charAt(0) || '?'}
  </Avatar>
);

const getOriginChip = (origin, theme) => {
  const isManual = origin === 'manual';
  return (
    <Chip
      size="small"
      label={isManual ? 'Manual' : 'Automated'}
      sx={{
        backgroundColor: isManual
          ? alpha(theme.palette.info.main, 0.12)
          : alpha(theme.palette.success.main, 0.12),
        color: isManual ? theme.palette.info.main : theme.palette.success.main,
        fontWeight: 600,
        fontSize: '0.75rem'
      }}
    />
  );
};

const DetailLabel = ({ children }) => (
  <Typography
    variant="caption"
    color="text.secondary"
    sx={{
      textTransform: 'uppercase',
      letterSpacing: 0.5,
      fontWeight: 500
    }}
  >
    {children}
  </Typography>
);

const RecordCard = ({
  record,
  isExpanded,
  isEditing,
  editForm,
  apps,
  canModifyRecords,
  canDeleteRecords,
  canResolveSyncConflicts,
  canViewRecordDetails,
  canViewPentestPage,
  onToggleExpanded,
  onUpdateEditForm,
  onStartEditing,
  onSave,
  onCancelEditing,
  onDelete,
  onResolveSyncConflict,
  onOpenHistory,
  onOpenPentest,
  theme
}) => {
  const hasSyncConflict = Boolean(record.sync_conflict);

  return (
    <Card
    sx={{
      mb: 1,
      backgroundColor: 'background.paper',
      border: `1px solid ${theme.palette.divider}`,
      '&:hover': {
        borderColor: theme.palette.primary.main,
        backgroundColor: alpha(theme.palette.primary.main, 0.02)
      },
      transition: 'all 0.2s ease-in-out'
    }}
  >
    <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
      <Box
        display="flex"
        alignItems={{ xs: 'flex-start', md: 'center' }}
        justifyContent="space-between"
        onClick={() => onToggleExpanded(record.id)}
        sx={{ cursor: 'pointer' }}
      >
        <Box display="flex" alignItems={{ xs: 'flex-start', md: 'center' }} flex={1} flexWrap="wrap">
          <IconButton size="small" sx={{ mr: 1 }}>
            {isExpanded ? <ExpandLess /> : <ExpandMore />}
          </IconButton>

          <Typography variant="h6" sx={{ mr: 2, fontWeight: 500 }}>
            {record.name}
          </Typography>

          <Typography variant="body2" color="text.secondary" sx={{ mr: 2, fontFamily: 'monospace' }}>
            {record.ip_address}
          </Typography>

          {record.application_name && (
            <Chip
              label={record.application_name}
              size="small"
              sx={{
                mr: 2,
                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                color: theme.palette.primary.main,
                fontWeight: 600
              }}
            />
          )}

          <Stack direction="row" spacing={1} sx={{ alignItems: 'center', flexWrap: 'wrap', rowGap: 1 }}>
            {getStatusChip(record.status, theme)}
            {getOriginChip(record.origin, theme)}
            {hasSyncConflict ? (
              <Chip
                size="small"
                color="error"
                label="Sync Conflict"
                sx={{ fontWeight: 600 }}
              />
            ) : null}
          </Stack>
        </Box>

        <Box display="flex" alignItems="center">
          {getSourceAvatar(record.source)}
          <Typography variant="body2" color="text.secondary" sx={{ mr: 2 }}>
            {record.source}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Modified {formatDateTime(record.last_modification_date)}
          </Typography>
        </Box>
      </Box>

      <Collapse in={isExpanded}>
        <Box sx={{ mt: 2 }}>
          <Divider sx={{ mb: 2 }} />

          <Grid container spacing={3}>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                Details
              </Typography>

              {isEditing ? (
                <Box>
                  <TextField
                    select
                    fullWidth
                    label="Application"
                    value={editForm.application_id}
                    onChange={(event) =>
                      onUpdateEditForm({ ...editForm, application_id: event.target.value })
                    }
                    sx={{ mb: 2 }}
                    size="small"
                  >
                    <MenuItem value="">Unassigned</MenuItem>
                    {apps.map((app) => (
                      <MenuItem key={app.id} value={app.id}>
                        {app.name}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    fullWidth
                    label="Application Owner"
                    value={editForm.application_owner}
                    onChange={(event) =>
                      onUpdateEditForm({ ...editForm, application_owner: event.target.value })
                    }
                    sx={{ mb: 2 }}
                    size="small"
                  />
                  <TextField
                    fullWidth
                    label="Maintainer"
                    value={editForm.maintainer}
                    onChange={(event) =>
                      onUpdateEditForm({ ...editForm, maintainer: event.target.value })
                    }
                    sx={{ mb: 2 }}
                    size="small"
                  />
                  <TextField
                    fullWidth
                    label="Open Ports"
                    value={editForm.open_ports}
                    onChange={(event) =>
                      onUpdateEditForm({ ...editForm, open_ports: event.target.value })
                    }
                    placeholder="22, 80, 443, 8080"
                    size="small"
                    multiline
                    rows={2}
                    helperText="Comma-separated port numbers (e.g., 22, 80, 443)"
                    InputProps={{
                      sx: { fontFamily: 'monospace' }
                    }}
                  />
                </Box>
              ) : (
                <Box
                  sx={{
                    display: 'grid',
                    gap: 2,
                    gridTemplateColumns: 'repeat(2, 1fr)',
                    alignItems: 'start'
                  }}
                >
                  <Box sx={{ minWidth: 100 }}>
                    <DetailLabel>Application</DetailLabel>
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 500,
                        color: record.application_name ? 'text.primary' : 'text.secondary'
                      }}
                    >
                      {record.application_name || 'Unassigned'}
                    </Typography>
                  </Box>
                  <Box sx={{ minWidth: 100 }}>
                    <DetailLabel>Owner</DetailLabel>
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 500,
                        color: record.application_owner ? 'text.primary' : 'text.secondary'
                      }}
                    >
                      {record.application_owner || 'Not assigned'}
                    </Typography>
                  </Box>

                  <Box sx={{ minWidth: 100 }}>
                    <DetailLabel>Maintainer</DetailLabel>
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 500,
                        color: record.maintainer ? 'text.primary' : 'text.secondary'
                      }}
                    >
                      {record.maintainer || 'Not assigned'}
                    </Typography>
                  </Box>

                  <Box sx={{ minWidth: 100 }}>
                    <DetailLabel>Open Ports</DetailLabel>
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: 500,
                        fontFamily: 'monospace',
                        color: record.open_ports ? 'text.primary' : 'text.secondary'
                      }}
                    >
                      {record.open_ports || 'None'}
                    </Typography>
                  </Box>
                </Box>
              )}
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" gutterBottom>
                Description
              </Typography>

              {isEditing ? (
                <Box>
                  <TextField
                    fullWidth
                    label="Description"
                    value={editForm.description}
                    onChange={(event) =>
                      onUpdateEditForm({ ...editForm, description: event.target.value })
                    }
                    size="small"
                    multiline
                    rows={3}
                    sx={{ mb: 2 }}
                  />
                </Box>
              ) : (
                <Box>
                  {hasSyncConflict ? (
                    <Box sx={{ mb: 2 }}>
                      <Typography variant="body2" color="error.main" sx={{ fontWeight: 600 }}>
                        This manual domain matches imported DNS data and requires admin resolution.
                      </Typography>
                    </Box>
                  ) : null}
                  <Typography variant="body2" color="text.secondary">
                    {record.description || 'No description'}
                  </Typography>
                </Box>
              )}
            </Grid>
          </Grid>

          <Box display="flex" justifyContent="flex-end" gap={1} sx={{ mt: 2 }}>
            {isEditing ? (
              <>
                <Button
                  variant="contained"
                  color="primary"
                  size="small"
                  startIcon={<Save />}
                  onClick={() => onSave(record.id)}
                >
                  Save
                </Button>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={<Cancel />}
                  onClick={onCancelEditing}
                >
                  Cancel
                </Button>
              </>
            ) : (
              <>
                {canModifyRecords && (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<Edit />}
                    onClick={() => onStartEditing(record)}
                  >
                    Edit
                  </Button>
                )}
                {canViewRecordDetails && (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<History />}
                    onClick={() => onOpenHistory(record)}
                  >
                    History
                  </Button>
                )}
                {canViewPentestPage && (
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<Security />}
                    onClick={() => onOpenPentest(record)}
                  >
                    Pentest
                  </Button>
                )}
                {hasSyncConflict && canResolveSyncConflicts && (
                  <Button
                    variant="outlined"
                    size="small"
                    color="warning"
                    startIcon={<SyncProblem />}
                    onClick={() => onResolveSyncConflict(record.id)}
                  >
                    Resolve Conflict
                  </Button>
                )}
                {canDeleteRecords && (
                  <Button
                    variant="outlined"
                    size="small"
                    color="error"
                    startIcon={<Delete />}
                    onClick={() => onDelete(record.id)}
                  >
                    Delete
                  </Button>
                )}
              </>
            )}
          </Box>
        </Box>
      </Collapse>
    </CardContent>
  </Card>
  );
};

export default RecordCard;
