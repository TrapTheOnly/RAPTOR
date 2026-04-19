import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  FormControlLabel,
  Grid,
  InputAdornment,
  Stack,
  Switch,
  TextField,
  Typography,
} from '@mui/material';
import { Save as SaveIcon, SmartToy as SmartToyIcon } from '@mui/icons-material';
import SectionHeader from './SectionHeader';

const ScannerSettingsPanel = ({ showMessage }) => {
  const [config, setConfig] = useState({
    aws_region: 'us-east-1',
    bedrock_model_id: '',
    cost_limit_usd: 5.0,
    input_cost_per_1m: 3.0,
    output_cost_per_1m: 15.0,
    max_concurrent_scans: 2,
    enabled: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await axios.get('/admin/scanner-config');
      if (res.data.config) {
        const c = res.data.config;
        setConfig({
          aws_region: c.aws_region || 'us-east-1',
          bedrock_model_id: c.bedrock_model_id || '',
          cost_limit_usd: Number(c.cost_limit_usd) || 5.0,
          input_cost_per_1m: Number(c.input_cost_per_1m) || 3.0,
          output_cost_per_1m: Number(c.output_cost_per_1m) || 15.0,
          max_concurrent_scans: Number(c.max_concurrent_scans) || 2,
          enabled: Boolean(Number(c.enabled ?? 0)),
        });
      }
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to load scanner config.');
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
    const maxConcurrent = Number(config.max_concurrent_scans);
    const costLimit = Number(config.cost_limit_usd);
    const inputCost = Number(config.input_cost_per_1m);
    const outputCost = Number(config.output_cost_per_1m);

    if (!Number.isInteger(maxConcurrent) || maxConcurrent < 1 || maxConcurrent > 10) {
      showMessage('error', 'Max Concurrent Scans must be an integer between 1 and 10.');
      return;
    }
    if (!costLimit || costLimit <= 0) {
      showMessage('error', 'Cost Limit must be greater than 0.');
      return;
    }
    if (!inputCost || inputCost <= 0) {
      showMessage('error', 'Input cost / 1M tokens must be greater than 0.');
      return;
    }
    if (!outputCost || outputCost <= 0) {
      showMessage('error', 'Output cost / 1M tokens must be greater than 0.');
      return;
    }

    setSaving(true);
    try {
      const payload = {
        ...config,
        cost_limit_usd: costLimit,
        input_cost_per_1m: inputCost,
        output_cost_per_1m: outputCost,
        max_concurrent_scans: maxConcurrent,
      };
      const res = await axios.put('/admin/scanner-config', payload);
      showMessage('success', res.data.message || 'Scanner configuration saved.');
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to save scanner config.');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return null;

  const showUnconfiguredWarning = config.enabled && !config.bedrock_model_id.trim();

  return (
    <Card>
      <CardContent>
        <SectionHeader icon={SmartToyIcon} title="AI Scanner" />

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Configure the AI-powered security scanner using AWS Bedrock. When enabled, users with
          owner or manager access can launch automated scans from pentest records.
        </Typography>

        {showUnconfiguredWarning && (
          <Alert severity="warning" sx={{ mb: 3 }}>
            Scanner is enabled but no Bedrock Model ID is configured. Scans will fail until a
            model ID is provided.
          </Alert>
        )}

        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Stack spacing={2.5}>
              <FormControlLabel
                control={
                  <Switch checked={config.enabled} onChange={handleChange('enabled')} />
                }
                label={
                  <Box>
                    <Typography variant="body2">Enable AI Scanner</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Allow users to launch AI-powered scans on pentest records
                    </Typography>
                  </Box>
                }
              />
              <TextField
                label="AWS Region"
                size="small"
                fullWidth
                value={config.aws_region}
                onChange={handleChange('aws_region')}
                placeholder="us-east-1"
              />
              <TextField
                label="Bedrock Model ID"
                size="small"
                fullWidth
                value={config.bedrock_model_id}
                onChange={handleChange('bedrock_model_id')}
                placeholder="arn:aws:bedrock:us-east-1:..."
                error={showUnconfiguredWarning}
              />
              <TextField
                label="Max Concurrent Scans"
                size="small"
                fullWidth
                type="number"
                value={config.max_concurrent_scans}
                onChange={handleChange('max_concurrent_scans')}
                inputProps={{ min: 1, max: 10 }}
                helperText="1–10 simultaneous scans"
              />
            </Stack>
          </Grid>

          <Grid item xs={12} md={6}>
            <Stack spacing={2.5}>
              <TextField
                label="Cost Limit (USD)"
                size="small"
                fullWidth
                type="number"
                value={config.cost_limit_usd}
                onChange={handleChange('cost_limit_usd')}
                inputProps={{ min: 0, step: 0.01 }}
                InputProps={{
                  startAdornment: <InputAdornment position="start">$</InputAdornment>,
                }}
                helperText="Abort scan if estimated cost exceeds this"
              />
              <TextField
                label="Input cost / 1M tokens"
                size="small"
                fullWidth
                type="number"
                value={config.input_cost_per_1m}
                onChange={handleChange('input_cost_per_1m')}
                inputProps={{ min: 0, step: 0.001 }}
                InputProps={{
                  startAdornment: <InputAdornment position="start">$</InputAdornment>,
                }}
              />
              <TextField
                label="Output cost / 1M tokens"
                size="small"
                fullWidth
                type="number"
                value={config.output_cost_per_1m}
                onChange={handleChange('output_cost_per_1m')}
                inputProps={{ min: 0, step: 0.001 }}
                InputProps={{
                  startAdornment: <InputAdornment position="start">$</InputAdornment>,
                }}
              />
            </Stack>
          </Grid>
        </Grid>

        <Box sx={{ mt: 3 }}>
          <Button
            variant="contained"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Settings'}
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ScannerSettingsPanel;
