import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Button,
  MetricStrip,
  Mono,
  ProviderMark,
  StatusGlyph,
  Text
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import { usePalette } from '../../../design/usePalette';
import SectionHeader from './SectionHeader';

const STATE_GLYPH = {
  ready: 'unchanged',
  error: 'missing',
  unavailable: 'missing',
  downloading: 'updated',
  verifying: 'updated',
  starting: 'updated',
  paused: 'retest',
  stopped: 'draft',
  not_installed: 'draft'
};

const STATE_LABEL = {
  ready: 'Ready',
  error: 'Error',
  unavailable: 'Runtime offline',
  downloading: 'Downloading',
  verifying: 'Verifying',
  starting: 'Starting',
  paused: 'Paused',
  stopped: 'Installed, stopped',
  not_installed: 'Not installed'
};

const formatBytes = (value) => {
  const n = Number(value) || 0;
  if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)} KB`;
  return `${n} B`;
};

const formatEta = (seconds) => {
  const n = Number(seconds);
  if (!Number.isFinite(n) || n <= 0) return '—';
  if (n < 90) return `${Math.round(n)}s`;
  if (n < 3600) return `${Math.round(n / 60)}m`;
  return `${Math.round(n / 3600)}h`;
};

const AiLocalModelPanel = ({ showMessage }) => {
  const palette = usePalette();
  const [status, setStatus] = useState({});
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const response = await axios.get('/admin/llm/local');
      setStatus(response.data?.status || {});
    } catch (error) {
      setStatus({
        state: 'unavailable',
        error: error.response?.data?.error || 'Local runtime is not running.'
      });
    }
  }, []);

  useEffect(() => {
    load();
    const handle = window.setInterval(load, 1200);
    return () => window.clearInterval(handle);
  }, [load]);

  const act = async (path, label) => {
    setBusy(true);
    try {
      await axios.post(`/admin/llm/local/${path}`);
      showMessage?.('success', label);
      await load();
    } catch (error) {
      showMessage?.('error', error.response?.data?.error || `Failed to ${path}.`);
      await load();
    } finally {
      setBusy(false);
    }
  };

  const state = String(status.state || 'not_installed');
  const percent = status.bytes_total
    ? Math.min(100, Math.round((Number(status.bytes_done || 0) / Number(status.bytes_total)) * 100))
    : 0;
  const active = ['downloading', 'verifying', 'starting'].includes(state);
  const ramWarn = Number(status.recommended_ram_gb || 24);
  const ramTotal = Number(status.ram_total_gb || 0);
  const ramLow = ramTotal > 0 && ramTotal < ramWarn;
  const diskWarn = Number(status.disk_free_bytes || 0) < 20 * 1e9;

  return (
    <div>
      <SectionHeader title="Local model">
        <ProviderMark type="local" size={22} />
      </SectionHeader>
      <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x16}px`, maxWidth: 640 }}>
        RAPTOR ships the Unsloth Qwen3.6-27B Q4 definition, not the weights. Install from here
        (~17.6 GB, Apache-2.0). This is the default when you do not want a hosted API.
      </Text>
      <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x12, marginBottom: SPACE.x16 }}>
        <StatusGlyph status={STATE_GLYPH[state] || 'draft'} label={STATE_LABEL[state] || state} />
        <div>
          <Text variant="bodyStrong">{status.display_name || 'Qwen3.6 27B (Unsloth Q4)'}</Text>
          <Text as="div" variant="meta" tone="secondary">
            {status.repo_id || 'unsloth/Qwen3.6-27B-GGUF'} · {status.quant || 'UD-Q4_K_XL'} ·{' '}
            {status.license || 'Apache-2.0'}
          </Text>
        </div>
      </div>
      <MetricStrip
        items={[
          { label: 'Disk free', value: formatBytes(status.disk_free_bytes), hint: diskWarn ? 'Need ~20 GB' : 'OK' },
          {
            label: 'RAM',
            value: ramTotal ? `${ramTotal} GB` : `${ramWarn} GB rec.`,
            hint: ramLow ? `Below ${ramWarn} GB rec.` : `${ramWarn} GB rec.`
          },
          { label: 'GPU', value: status.gpu ? 'Detected' : 'CPU', hint: status.gpu ? `${status.recommended_vram_gb || 18} GB VRAM rec.` : 'Allowed, slow' },
          { label: 'Context', value: String(status.context_length || 8192), hint: 'Scanner default' }
        ]}
      />
      {active || state === 'paused' ? (
        <div style={{ marginBottom: SPACE.x16 }}>
          <div
            style={{
              height: 6,
              borderRadius: 99,
              background: palette.line,
              overflow: 'hidden'
            }}
          >
            <div
              style={{
                width: `${percent}%`,
                height: '100%',
                background: palette.accent
              }}
            />
          </div>
          <Mono style={{ display: 'block', marginTop: 8 }}>
            {percent}% · {formatBytes(status.bytes_done)} / {formatBytes(status.bytes_total)} ·{' '}
            {formatBytes(status.speed_bps)}/s · ETA {formatEta(status.eta_seconds)}
          </Mono>
        </div>
      ) : null}
      {status.error ? (
        <Text as="p" variant="meta" tone="secondary" style={{ marginBottom: SPACE.x16 }}>
          {status.error}
        </Text>
      ) : null}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: SPACE.x8 }}>
        {state === 'not_installed' || state === 'error' || state === 'unavailable' ? (
          <Button variant="contained" size="small" disabled={busy} onClick={() => act('install', 'Install started.')}>
            Install
          </Button>
        ) : null}
        {state === 'downloading' ? (
          <>
            <Button size="small" disabled={busy} onClick={() => act('pause', 'Download paused.')}>
              Pause
            </Button>
            <Button size="small" disabled={busy} onClick={() => act('cancel', 'Download cancelled.')}>
              Cancel
            </Button>
          </>
        ) : null}
        {state === 'paused' ? (
          <Button variant="contained" size="small" disabled={busy} onClick={() => act('resume', 'Download resumed.')}>
            Resume
          </Button>
        ) : null}
        {state === 'stopped' ? (
          <Button variant="contained" size="small" disabled={busy} onClick={() => act('start', 'Runtime starting.')}>
            Start
          </Button>
        ) : null}
        {state === 'ready' ? (
          <Button size="small" disabled={busy} onClick={() => act('stop', 'Runtime stopped.')}>
            Stop
          </Button>
        ) : null}
        {['stopped', 'ready', 'error', 'paused'].includes(state) ? (
          <Button size="small" disabled={busy} onClick={() => act('uninstall', 'Model removed.')}>
            Uninstall
          </Button>
        ) : null}
        <Button size="small" disabled={busy} onClick={load}>
          Recheck
        </Button>
      </div>
    </div>
  );
};

export default AiLocalModelPanel;
