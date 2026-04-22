import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Box,
  Button,
  Card,
  CardContent,
  FormControlLabel,
  Grid,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import {
  CheckCircleOutline as ConnectIcon,
  Email as EmailIcon,
  Save as SaveIcon,
  Send as SendIcon,
} from '@mui/icons-material';
import SectionHeader from './SectionHeader';

const EmailSettingsPanel = ({ showMessage }) => {
  const [config, setConfig] = useState({
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_password: '',
    smtp_use_tls: true,
    sender_email: '',
    sender_name: 'RAPTOR',
    enabled: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [testRecipient, setTestRecipient] = useState('');

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get('/admin/email-config');
      if (res.data.config) {
        const c = res.data.config;
        setConfig({
          smtp_host: c.smtp_host || '',
          smtp_port: c.smtp_port || 587,
          smtp_user: c.smtp_user || '',
          smtp_password: c.smtp_password || '',
          smtp_use_tls: Boolean(Number(c.smtp_use_tls ?? 1)),
          sender_email: c.sender_email || '',
          sender_name: c.sender_name || 'RAPTOR',
          enabled: Boolean(Number(c.enabled ?? 0)),
        });
      }
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to load email config.');
    } finally {
      setLoading(false);
    }
  }, [showMessage]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleChange = (field) => (event) => {
    const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
    setConfig((prev) => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    if (!config.smtp_host || !config.sender_email) {
      showMessage('error', 'SMTP Host and Sender Email are required.');
      return;
    }
    setSaving(true);
    try {
      const res = await axios.post('/admin/email-config', config);
      showMessage('success', res.data.message || 'Email configuration saved.');
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to save email config.');
    } finally {
      setSaving(false);
    }
  };

  const handleTestConnection = async () => {
    setConnecting(true);
    try {
      const res = await axios.post('/admin/email-config/test-connection');
      showMessage('success', res.data.message || 'SMTP connection successful.');
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'SMTP connection failed.');
    } finally {
      setConnecting(false);
    }
  };

  const handleTest = async () => {
    if (!testRecipient || !testRecipient.includes('@')) {
      showMessage('error', 'Enter a valid recipient email address.');
      return;
    }
    setTesting(true);
    try {
      const res = await axios.post('/admin/email-config/test', { to_email: testRecipient });
      showMessage('success', res.data.message || 'Test email sent.');
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to send test email.');
    } finally {
      setTesting(false);
    }
  };

  if (loading) return null;

  return (
    <Card>
      <CardContent>
        <SectionHeader icon={EmailIcon} title="Email Notifications" />

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Configure SMTP settings to enable email notifications for events like collaborator
          assignments and zone sync results.
        </Typography>

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Stack spacing={2.5}>
              <TextField
                label="SMTP Host"
                size="small"
                fullWidth
                value={config.smtp_host}
                onChange={handleChange('smtp_host')}
                placeholder="smtp.example.com"
              />
              <TextField
                label="SMTP Port"
                size="small"
                fullWidth
                type="number"
                value={config.smtp_port}
                onChange={handleChange('smtp_port')}
              />
              <TextField
                label="SMTP Username"
                size="small"
                fullWidth
                value={config.smtp_user}
                onChange={handleChange('smtp_user')}
                autoComplete="off"
              />
              <TextField
                label="SMTP Password"
                size="small"
                fullWidth
                type="password"
                value={config.smtp_password}
                onChange={handleChange('smtp_password')}
                autoComplete="new-password"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={config.smtp_use_tls}
                    onChange={handleChange('smtp_use_tls')}
                  />
                }
                label="Use STARTTLS"
              />
            </Stack>
          </Grid>

          <Grid item xs={12} md={6}>
            <Stack spacing={2.5}>
              <TextField
                label="Sender Email"
                size="small"
                fullWidth
                value={config.sender_email}
                onChange={handleChange('sender_email')}
                placeholder="raptor@example.com"
              />
              <TextField
                label="Sender Name"
                size="small"
                fullWidth
                value={config.sender_name}
                onChange={handleChange('sender_name')}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={config.enabled}
                    onChange={handleChange('enabled')}
                  />
                }
                label={
                  <Box>
                    <Typography variant="body2">Enable Email Notifications</Typography>
                    <Typography variant="caption" color="text.secondary">
                      When disabled, only in-app notifications are created
                    </Typography>
                  </Box>
                }
              />
            </Stack>
          </Grid>
        </Grid>

        <Box sx={{ mt: 3, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </Button>
            <Button
              variant="outlined"
              startIcon={<ConnectIcon />}
              onClick={handleTestConnection}
              disabled={connecting}
            >
              {connecting ? 'Connecting...' : 'Test Connection'}
            </Button>
          </Box>
          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
            <TextField
              label="Test Recipient Email"
              size="small"
              value={testRecipient}
              onChange={(e) => setTestRecipient(e.target.value)}
              placeholder="you@example.com"
              sx={{ minWidth: 260 }}
            />
            <Button
              variant="outlined"
              startIcon={<SendIcon />}
              onClick={handleTest}
              disabled={testing}
            >
              {testing ? 'Sending...' : 'Send Test Email'}
            </Button>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default EmailSettingsPanel;
