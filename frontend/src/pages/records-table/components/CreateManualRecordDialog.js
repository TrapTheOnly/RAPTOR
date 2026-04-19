import React from 'react';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography
} from '@mui/material';

const CreateManualRecordDialog = ({
  open,
  form,
  apps,
  busy,
  error,
  onClose,
  onChange,
  onSubmit
}) => (
  <Dialog open={open} onClose={busy ? undefined : onClose} fullWidth maxWidth="sm">
    <DialogTitle>Add Manual Domain</DialogTitle>
    <DialogContent>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Manual domains stay in the main registry and can later be adopted into automated sync if an
        imported zone file starts publishing the same domain.
      </Typography>
      <Stack spacing={2} sx={{ mt: 1 }}>
        <TextField
          label="Domain"
          value={form.name}
          onChange={(event) => onChange('name', event.target.value)}
          placeholder="api.example.com"
          required
          fullWidth
          autoFocus
        />
        <TextField
          label="IP Address"
          value={form.ip_address}
          onChange={(event) => onChange('ip_address', event.target.value)}
          placeholder="10.10.10.10"
          required
          fullWidth
        />
        <TextField
          select
          label="Application"
          value={form.application_id}
          onChange={(event) => onChange('application_id', event.target.value)}
          fullWidth
        >
          <MenuItem value="">Unassigned</MenuItem>
          {apps.map((app) => (
            <MenuItem key={app.id} value={app.id}>
              {app.name}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          label="Application Owner"
          value={form.application_owner}
          onChange={(event) => onChange('application_owner', event.target.value)}
          fullWidth
        />
        <TextField
          label="Maintainer"
          value={form.maintainer}
          onChange={(event) => onChange('maintainer', event.target.value)}
          fullWidth
        />
        <TextField
          label="Open Ports"
          value={form.open_ports}
          onChange={(event) => onChange('open_ports', event.target.value)}
          placeholder="22, 80, 443"
          fullWidth
        />
        <TextField
          label="Description"
          value={form.description}
          onChange={(event) => onChange('description', event.target.value)}
          multiline
          rows={3}
          fullWidth
        />
        {error ? (
          <Typography variant="body2" color="error">
            {error}
          </Typography>
        ) : null}
      </Stack>
    </DialogContent>
    <DialogActions>
      <Button onClick={onClose} disabled={busy}>
        Cancel
      </Button>
      <Button onClick={onSubmit} variant="contained" disabled={busy}>
        Create
      </Button>
    </DialogActions>
  </Dialog>
);

export default CreateManualRecordDialog;
