import React, { useEffect, useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Alert } from '@mui/material';
import { Download, LinkOff } from '@mui/icons-material';
import { Button, Mono, Tag, Text } from '../../../design/primitives';
import { getWaveBurp, mintBurpToken, revokeBurpToken, startBurpAnalyze } from '../services';

const formatWhen = (value) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
};

const BurpLiveSection = ({ appId, waveId, canMint, isOpen }) => {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const reload = async () => {
    if (!appId || !waveId) return;
    const response = await getWaveBurp(appId, waveId);
    setStatus(response.data);
  };

  useEffect(() => {
    let cancelled = false;
    getWaveBurp(appId, waveId)
      .then((response) => {
        if (!cancelled) setStatus(response.data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.error || 'Could not load Burp Live status.');
      });
    return () => {
      cancelled = true;
    };
  }, [appId, waveId]);

  const mint = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await mintBurpToken(appId, waveId);
      setToken(response.data.token || '');
      await reload();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not mint a wave token.');
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    setError('');
    try {
      await revokeBurpToken(appId, waveId);
      setToken('');
      await reload();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not revoke the Burp token.');
    } finally {
      setBusy(false);
    }
  };

  const startAnalyze = async () => {
    setBusy(true);
    setError('');
    try {
      const response = await startBurpAnalyze(appId, waveId);
      const engagementId = response.data?.engagement_id;
      if (engagementId) {
        navigate(`/apps/${appId}/waves/${waveId}/scan-live?engagement=${encodeURIComponent(engagementId)}`);
        return;
      }
      await reload();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not start Burp event analysis.');
    } finally {
      setBusy(false);
    }
  };

  const jarAvailable = Boolean(status?.jar?.available);
  const enroll = status?.enroll;
  const agents = status?.agents || [];

  return (
    <section>
      <Text as="div" variant="h2" style={{ marginBottom: 8 }}>
        Burp Live
      </Text>
      <Text as="p" variant="meta" tone="secondary" style={{ margin: '0 0 12px', maxWidth: 640 }}>
        Start happens in Burp, never here. Download the JAR, mint a wave token, load the extension,
        and click Start on the RAPTOR tab. Repeater and Intruder stream here live. Summarize Burp
        traffic when you want RAPTOR to cluster that notebook into an Analyze engagement — ingest
        never starts an AI scan. JWT analysis is a separate send from Burp, and both show up on{' '}
        {appId && waveId ? (
          <RouterLink to={`/apps/${appId}/waves/${waveId}/scan-live`}>Live progress</RouterLink>
        ) : (
          'Live progress'
        )}
        . RAPTOR does not open a connection to your laptop.
      </Text>
      {error ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      ) : null}
      {token ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          Copy this token into Burp now. RAPTOR stores only a hash.
          <Mono style={{ display: 'block', marginTop: 8, wordBreak: 'break-all' }}>{token}</Mono>
        </Alert>
      ) : null}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <Button
          size="small"
          variant="outlined"
          startIcon={<Download sx={{ fontSize: 16 }} />}
          href="/burp/v1/download/raptor-burp.jar"
          disabled={!jarAvailable}
        >
          Download JAR
        </Button>
        {canMint && isOpen ? (
          <Button size="small" variant="contained" onClick={mint} disabled={busy}>
            Mint wave token
          </Button>
        ) : null}
        {canMint && isOpen ? (
          <Button
            size="small"
            variant="contained"
            onClick={startAnalyze}
            disabled={busy || !(status?.event_count > 0)}
          >
            Summarize Burp traffic
          </Button>
        ) : null}
        {canMint && enroll && !enroll.revoked ? (
          <Button size="small" startIcon={<LinkOff sx={{ fontSize: 16 }} />} onClick={revoke} disabled={busy}>
            Revoke
          </Button>
        ) : null}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Tag>{jarAvailable ? `JAR ${status?.jar?.version || ''}` : 'JAR not built yet'}</Tag>
        {enroll ? (
          <Tag>
            {enroll.revoked ? 'token revoked' : enroll.used ? 'token used' : 'token ready'}
          </Tag>
        ) : (
          <Tag>no token</Tag>
        )}
        <Tag>{`${status?.event_count || 0} events`}</Tag>
      </div>
      {agents.length ? (
        <div style={{ marginTop: 12 }}>
          {agents.map((agent) => (
            <Text key={agent.id} as="p" variant="meta" tone="secondary" style={{ margin: '4px 0' }}>
              {agent.hostname || 'Burp'} · {agent.status}
              {agent.last_heartbeat_at ? ` · last seen ${formatWhen(agent.last_heartbeat_at)}` : ''}
            </Text>
          ))}
        </div>
      ) : (
        <Text as="p" variant="meta" tone="secondary" style={{ marginTop: 12 }}>
          No Burp session has enrolled on this wave yet.
        </Text>
      )}
    </section>
  );
};

export default BurpLiveSection;
