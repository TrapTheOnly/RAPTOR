import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Checkbox,
  Chip,
  Divider,
  FormControlLabel,
  List,
  ListItemButton,
  ListItemText,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import {
  Autorenew as RotateIcon,
  ContentCopy as CopyIcon,
  Key as KeyIcon,
  Visibility as ViewIcon
} from '@mui/icons-material';
import SectionHeader from '../SectionHeader';

const SCOPE_OPTIONS = [
  { key: 'records.read', label: 'View Assets Dataset' },
  { key: 'pentests.read', label: 'View Pentests Dataset' }
];

const ServiceAccountsPanel = ({
  loading,
  serviceAccounts,
  selectedServiceAccountUsername,
  onSelectServiceAccount,
  createUsername,
  setCreateUsername,
  createScopes,
  onToggleCreateScope,
  createEndDate,
  setCreateEndDate,
  onCreateServiceAccountWithKey,
  selectedScopes,
  onToggleSelectedScope,
  selectedEndDate,
  setSelectedEndDate,
  onCreateKeyForSelectedServiceAccount,
  onSaveSelectedScopes,
  onViewSelectedKey,
  onRotateSelectedKey,
  visibleApiKey,
  onCopyVisibleApiKey
}) => {
  const selectedAccount =
    serviceAccounts.find((account) => account.username === selectedServiceAccountUsername) || null;

  return (
    <Stack spacing={3}>
      <SectionHeader icon={KeyIcon} title="Service Accounts and API Keys" />

      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
            Create Service Account + API Key
          </Typography>
          <Stack spacing={1.5}>
            <TextField
              label="Service account username"
              value={createUsername}
              onChange={(event) => setCreateUsername(event.target.value)}
              placeholder="svc.integrations"
              size="small"
              fullWidth
            />
            <Box>
              <Typography variant="caption" color="text.secondary">
                Privileges
              </Typography>
              <Stack>
                {SCOPE_OPTIONS.map((scope) => (
                  <FormControlLabel
                    key={scope.key}
                    control={
                      <Checkbox
                        checked={createScopes.includes(scope.key)}
                        onChange={() => onToggleCreateScope(scope.key)}
                      />
                    }
                    label={scope.label}
                  />
                ))}
              </Stack>
            </Box>
            <TextField
              type="date"
              label="Initial key end date (optional)"
              InputLabelProps={{ shrink: true }}
              value={createEndDate}
              onChange={(event) => setCreateEndDate(event.target.value)}
              size="small"
              helperText="Default is 90 days if blank."
            />
            <Button
              variant="contained"
              startIcon={<KeyIcon />}
              onClick={onCreateServiceAccountWithKey}
              disabled={loading}
            >
              Create Service Account
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <Card variant="outlined">
        <CardContent>
          <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 1 }}>
            Existing Service Accounts
          </Typography>
          {serviceAccounts.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No service accounts found.
            </Typography>
          ) : (
            <List dense sx={{ border: 1, borderColor: 'divider', borderRadius: 1 }}>
              {serviceAccounts.map((account) => (
                <ListItemButton
                  key={account.username}
                  selected={selectedServiceAccountUsername === account.username}
                  onClick={() => onSelectServiceAccount(account.username)}
                >
                  <ListItemText
                    primary={account.username}
                    secondary={
                      account.has_api_key
                        ? `Expires: ${account.expires_at || 'Not set'}`
                        : 'No API key'
                    }
                  />
                  <Chip
                    size="small"
                    color={account.has_api_key ? 'success' : 'default'}
                    label={account.has_api_key ? 'Key active' : 'No key'}
                  />
                </ListItemButton>
              ))}
            </List>
          )}
        </CardContent>
      </Card>

      {selectedAccount && (
        <Card variant="outlined">
          <CardContent>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {selectedAccount.username}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Created: {selectedAccount.added_date || 'Unknown'}
            </Typography>

            <Divider sx={{ my: 2 }} />

            <Box>
              <Typography variant="caption" color="text.secondary">
                Privileges
              </Typography>
              <Stack>
                {SCOPE_OPTIONS.map((scope) => (
                  <FormControlLabel
                    key={scope.key}
                    control={
                      <Checkbox
                        checked={selectedScopes.includes(scope.key)}
                        onChange={() => onToggleSelectedScope(scope.key)}
                        disabled={!selectedAccount.has_api_key}
                      />
                    }
                    label={scope.label}
                  />
                ))}
              </Stack>
              <Button
                variant="outlined"
                onClick={onSaveSelectedScopes}
                disabled={loading || !selectedAccount.has_api_key}
              >
                Save Privileges
              </Button>
            </Box>

            <Divider sx={{ my: 2 }} />

            {!selectedAccount.has_api_key ? (
              <Stack spacing={1.5}>
                <Typography variant="body2" color="text.secondary">
                  This service account has no API key yet.
                </Typography>
                <TextField
                  type="date"
                  label="Initial key end date (optional)"
                  InputLabelProps={{ shrink: true }}
                  value={selectedEndDate}
                  onChange={(event) => setSelectedEndDate(event.target.value)}
                  size="small"
                  helperText="Default is 90 days if blank."
                />
                <Button
                  variant="contained"
                  startIcon={<KeyIcon />}
                  onClick={onCreateKeyForSelectedServiceAccount}
                  disabled={loading}
                >
                  Create API Key
                </Button>
              </Stack>
            ) : (
              <Stack spacing={1.5}>
                <Typography variant="body2" color="text.secondary">
                  Key created: {selectedAccount.key_created_at || 'Unknown'} | Expires:{' '}
                  {selectedAccount.expires_at || 'Unknown'}
                </Typography>
                <Stack direction="row" spacing={1}>
                  <Button
                    variant="outlined"
                    startIcon={<ViewIcon />}
                    onClick={onViewSelectedKey}
                    disabled={loading}
                  >
                    View API Key
                  </Button>
                  <Button
                    variant="contained"
                    color="warning"
                    startIcon={<RotateIcon />}
                    onClick={onRotateSelectedKey}
                    disabled={loading}
                  >
                    Rotate Key
                  </Button>
                </Stack>
              </Stack>
            )}

            {visibleApiKey && (
              <Alert
                severity="info"
                sx={{ mt: 2 }}
                action={
                  <Button
                    color="inherit"
                    size="small"
                    startIcon={<CopyIcon />}
                    onClick={onCopyVisibleApiKey}
                  >
                    Copy
                  </Button>
                }
              >
                <Typography variant="body2" sx={{ wordBreak: 'break-all' }}>
                  {visibleApiKey}
                </Typography>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}
    </Stack>
  );
};

export default ServiceAccountsPanel;
