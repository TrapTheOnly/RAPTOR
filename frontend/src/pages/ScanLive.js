import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link as RouterLink, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowBack, Monitor, RestartAlt, SmartToy, Stop } from '@mui/icons-material';
import {
  Button,
  DataList,
  DataRow,
  EmptyState,
  Field,
  MetricStrip,
  Mono,
  Page,
  PageHeader,
  ProviderMark,
  Surface,
  SwitchRow,
  Tag,
  Text,
  Toast
} from '../design/primitives';
import { FONTS, RADIUS, SPACE } from '../design/tokens';
import { usePalette } from '../design/usePalette';
import { getWave, launchWaveScan, resetWaveScan, stopWaveScan } from './app-workspace/services';
import { fetchPentestRecord } from './pentest-record/services';

const MAX_FEED_EVENTS = 200;
const DETAIL_CHARS = 220;

const HIDDEN_TOOLS = new Set([
  'log_scan_event',
  'set_scan_status',
  'notify_scan_complete',
  'get_pentest',
  'get_checklist_templates',
  'update_checklist_item',
  'get_or_create_vuln_category'
]);

const TOOL_LABELS = {
  nmap_scan: 'nmap',
  nuclei_scan: 'nuclei',
  nikto_scan: 'nikto',
  gobuster_scan: 'gobuster',
  ffuf_scan: 'ffuf',
  dirb_scan: 'dirb',
  wpscan_analyze: 'wpscan',
  sqlmap_scan: 'sqlmap',
  enum4linux_scan: 'enum4linux',
  hydra_attack: 'hydra',
  execute_command: 'command',
  update_pentest_ports: 'ports',
  add_pentest_vulnerability: 'finding'
};

function formatTs(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString();
  } catch {
    return ts;
  }
}

function toEpochMs(ts) {
  if (!ts) return null;
  const value = new Date(ts).getTime();
  return Number.isFinite(value) ? value : null;
}

function formatTokens(n) {
  const value = Number(n) || 0;
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return String(value);
}

function shortHost(name) {
  const raw = String(name || '').trim();
  if (!raw) return '';
  return raw.split('.')[0];
}

function hostColor(palette, hostId) {
  const colors = [
    palette.accent,
    palette.lifecycle?.deferred,
    palette.severity?.high,
    palette.lifecycle?.positive
  ].filter(Boolean);
  if (!colors.length) return palette.accent;
  const index = Math.abs(Number(hostId) || 0) % colors.length;
  return colors[index];
}

function toolLabel(name) {
  return TOOL_LABELS[name] || String(name || 'tool').replace(/_/g, ' ');
}

function clip(text, max = DETAIL_CHARS) {
  const value = String(text || '').replace(/\s+/g, ' ').trim();
  if (!value) return '';
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

function detailFromInput(snippet) {
  const raw = String(snippet || '').trim();
  if (!raw) return '';
  try {
    const parsed = JSON.parse(raw.replace(/…$/, ''));
    if (parsed && typeof parsed === 'object') {
      const bits = [];
      ['command', 'target', 'url', 'host', 'ports', 'title', 'query', 'path', 'name', 'scan_type'].forEach((key) => {
        if (parsed[key]) bits.push(String(parsed[key]));
      });
      if (bits.length) return bits.join(' · ');
    }
  } catch {
    /* keep raw snippet */
  }
  return raw;
}

function foldEvents(raw) {
  const rows = [];
  for (const ev of raw) {
    const payload = ev.payload || {};
    const type = ev.event_type;
    if (type === 'api_call') continue;
    if (type === 'status') {
      if (payload.wave_complete || payload.scan_status === 'completed' || payload.scan_status === 'failed') {
        const stopped = payload.reason === 'stopped';
        const title = stopped ? 'Scan stopped' : payload.scan_status === 'failed' ? 'Scan failed' : 'Scan complete';
        const last = rows[rows.length - 1];
        if (last && last.kind === 'outcome' && last.title === title) continue;
        rows.push({
          id: ev.id,
          kind: 'outcome',
          title,
          detail: clip(payload.reason && payload.reason !== 'stopped' ? payload.reason : ''),
          recordId: ev.record_id,
          ts: ev.ts,
          error: payload.scan_status === 'failed' && !stopped
        });
        continue;
      }
      const title = payload.message || (payload.section ? payload.section : payload.phase);
      if (payload.phase === 'port_discovery' || payload.phase === 'testing' || payload.message) {
        rows.push({
          id: ev.id,
          kind: 'phase',
          title: title || 'Working',
          detail: clip(
            [payload.section, payload.message && payload.message !== title ? payload.message : '']
              .filter(Boolean)
              .join(' · ')
          ),
          recordId: payload.record_id || ev.record_id,
          ts: ev.ts
        });
      }
      continue;
    }
    if (type === 'finding') {
      rows.push({
        id: ev.id,
        kind: 'finding',
        title: payload.title || (payload.findings_count ? `Finding ${payload.findings_count}` : 'Finding'),
        detail: clip(payload.severity || payload.summary || ''),
        recordId: ev.record_id,
        ts: ev.ts
      });
      continue;
    }
    if (type === 'tool_call') {
      if (HIDDEN_TOOLS.has(payload.tool_name)) continue;
      const input = detailFromInput(payload.input_snippet);
      rows.push({
        id: ev.id,
        kind: 'tool',
        tool: payload.tool_name,
        title: toolLabel(payload.tool_name),
        detail: clip(input),
        input,
        source: payload.mcp_source,
        pending: true,
        error: false,
        recordId: ev.record_id,
        ts: ev.ts
      });
      continue;
    }
    if (type === 'tool_result') {
      if (HIDDEN_TOOLS.has(payload.tool_name)) continue;
      const result = clip(payload.result_snippet);
      let matched = false;
      for (let i = rows.length - 1; i >= 0; i -= 1) {
        if (rows[i].kind === 'tool' && rows[i].pending && rows[i].tool === payload.tool_name) {
          const input = rows[i].input || rows[i].detail;
          rows[i] = {
            ...rows[i],
            pending: false,
            error: Boolean(payload.is_error),
            detail: clip([input, result].filter(Boolean).join(' → '))
          };
          matched = true;
          break;
        }
      }
      if (!matched) {
        rows.push({
          id: ev.id,
          kind: 'tool',
          tool: payload.tool_name,
          title: toolLabel(payload.tool_name),
          detail: result,
          source: payload.mcp_source,
          pending: false,
          error: Boolean(payload.is_error),
          recordId: ev.record_id,
          ts: ev.ts
        });
      }
    }
  }
  return rows;
}

const HostChip = ({ active, color, children, onClick, style }) => (
  <button
    type="button"
    onClick={onClick}
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      height: 22,
      padding: '0 8px',
      borderRadius: RADIUS.chip,
      border: `1px solid ${color}`,
      color,
      background: active ? `color-mix(in srgb, ${color} 16%, transparent)` : 'transparent',
      cursor: 'pointer',
      fontFamily: FONTS.mono,
      fontSize: 11,
      fontWeight: 500,
      letterSpacing: '0.04em',
      textTransform: 'uppercase',
      whiteSpace: 'nowrap',
      ...style
    }}
  >
    {children}
  </button>
);

const HostScanLiveRedirect = () => {
  const { recordId } = useParams();
  const [searchParams] = useSearchParams();
  const waveId = searchParams.get('wave');
  const [record, setRecord] = useState(undefined);

  useEffect(() => {
    let cancelled = false;
    fetchPentestRecord(recordId)
      .then((response) => {
        if (!cancelled) setRecord(response.data || null);
      })
      .catch(() => {
        if (!cancelled) setRecord(null);
      });
    return () => {
      cancelled = true;
    };
  }, [recordId]);

  if (record === undefined) return <Page />;
  if (record?.application_id && waveId) {
    return <Navigate to={`/apps/${record.application_id}/waves/${waveId}/scan-live`} replace />;
  }
  const appTo = record?.application_id ? `/apps/${record.application_id}` : '/pentest';
  return (
    <Page>
      <EmptyState
        icon={Monitor}
        title="Launch from the wave"
        hint="Open the application, start the wave, then launch the AI scan from there."
        actions={
          <Button size="small" component={RouterLink} to={appTo}>
            Open application
          </Button>
        }
      />
    </Page>
  );
};

const WaveScanLive = () => {
  const { appId, waveId } = useParams();
  const palette = usePalette();
  const [wave, setWave] = useState(null);
  const [hosts, setHosts] = useState([]);
  const [appName, setAppName] = useState('');
  const [hostFilter, setHostFilter] = useState('all');
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState({
    scan_status: 'idle',
    findings: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    provider: ''
  });
  const [currentTool, setCurrentTool] = useState(null);
  const [done, setDone] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [scanStarted, setScanStarted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [operatorBrief, setOperatorBrief] = useState('');
  const [maxTurns, setMaxTurns] = useState('');
  const [skipPorts, setSkipPorts] = useState(false);
  const [toast, setToast] = useState({ open: false, message: '', severity: 'error' });
  const startTimeRef = useRef(null);
  const feedRef = useRef(null);
  const lastIdRef = useRef(0);
  const [sseKey, setSseKey] = useState(0);

  const scopedHosts = useMemo(
    () => (hosts || []).filter((host) => host.in_scope !== false),
    [hosts]
  );
  const hostById = useMemo(() => {
    const map = new Map();
    scopedHosts.forEach((host) => map.set(Number(host.id), host));
    return map;
  }, [scopedHosts]);

  const loadWave = useCallback(async () => {
    try {
      const response = await getWave(appId, waveId);
      const data = response.data || {};
      setWave(data.wave || null);
      setHosts(data.hosts || []);
      setAppName(data.wave?.application_name || '');
      const job = data.current_scan_job || data.wave?.current_scan_job || {};
      const jobStatus = String(job.status || '');
      const jobError = String(job.last_error || '');
      const hostStatuses = (data.hosts || [])
        .filter((host) => host.in_scope !== false)
        .map((host) => String(host.scan_status || 'idle'));
      let status = jobStatus === 'running' || hostStatuses.includes('running')
        ? 'running'
        : hostStatuses.includes('failed')
          ? 'failed'
          : hostStatuses.includes('completed')
            ? 'completed'
            : 'idle';
      if (status === 'failed' && jobError === 'stopped') status = 'stopped';
      setStats((prev) => ({ ...prev, scan_status: status }));
      if (status === 'running') {
        setScanStarted(true);
        setDone(false);
      }
      if (status === 'completed' || status === 'failed' || status === 'stopped') {
        setDone(true);
      }
    } catch {
      setWave(null);
      setHosts([]);
    }
  }, [appId, waveId]);

  useEffect(() => {
    loadWave();
  }, [loadWave]);

  const applyEvent = useCallback((ev) => {
    const { event_type, payload = {}, ts, id } = ev;
    lastIdRef.current = id;
    setEvents((prev) => {
      const next = [...prev, ev];
      return next.length > MAX_FEED_EVENTS ? next.slice(next.length - MAX_FEED_EVENTS) : next;
    });

    if (event_type === 'status') {
      const stopped = payload.reason === 'stopped';
      const status = stopped ? 'stopped' : payload.scan_status;
      setStats((s) => ({
        ...s,
        scan_status: status || s.scan_status,
        findings: payload.findings_count ?? s.findings,
        input_tokens: payload.input_tokens ?? s.input_tokens,
        output_tokens: payload.output_tokens ?? s.output_tokens,
        cost_usd: payload.cost_usd ?? s.cost_usd
      }));
      if ((status === 'running' || payload.phase) && !startTimeRef.current) {
        const eventTimeMs = toEpochMs(ts);
        startTimeRef.current = eventTimeMs || Date.now();
        setElapsedMs(Math.max(0, Date.now() - startTimeRef.current));
        setScanStarted(true);
      }
      if (payload.wave_complete || status === 'completed' || status === 'failed' || stopped) {
        setCurrentTool(null);
        setDone(true);
      }
    } else if (event_type === 'api_call') {
      setStats((s) => ({
        ...s,
        input_tokens: payload.total_input_tokens ?? s.input_tokens,
        output_tokens: payload.total_output_tokens ?? s.output_tokens,
        cost_usd: payload.cost_usd ?? s.cost_usd,
        provider: payload.provider || s.provider
      }));
    } else if (event_type === 'tool_call') {
      if (!HIDDEN_TOOLS.has(payload.tool_name)) {
        setCurrentTool({
          name: payload.tool_name,
          source: payload.mcp_source,
          recordId: ev.record_id,
          detail: clip(detailFromInput(payload.input_snippet), 120)
        });
      }
    } else if (event_type === 'tool_result') {
      setCurrentTool(null);
    } else if (event_type === 'finding') {
      setStats((s) => ({ ...s, findings: payload.findings_count ?? s.findings + 1 }));
    }
  }, []);

  useEffect(() => {
    if (done) return undefined;
    const url = `/api/apps/${appId}/waves/${waveId}/scan-events/stream?after=${lastIdRef.current}`;
    const es = new EventSource(url);
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.__done__) {
          setDone(true);
          es.close();
          return;
        }
        applyEvent(data);
      } catch {
        /* heartbeat */
      }
    };
    es.onerror = () => {
      es.close();
      if (!done) setTimeout(() => setSseKey((k) => k + 1), 3000);
    };
    return () => es.close();
  }, [appId, waveId, done, applyEvent, sseKey]);

  useEffect(() => {
    if (done || !scanStarted) return undefined;
    const iv = setInterval(() => setElapsedMs(Date.now() - (startTimeRef.current || Date.now())), 500);
    return () => clearInterval(iv);
  }, [done, scanStarted]);

  useEffect(() => {
    if (done || !scanStarted) return undefined;
    const iv = setInterval(() => {
      loadWave();
    }, 12000);
    return () => clearInterval(iv);
  }, [done, scanStarted, loadWave]);

  useEffect(() => {
    if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [events, hostFilter]);

  const failWith = (error, fallback) => {
    setToast({
      open: true,
      message: error?.response?.data?.error || fallback,
      severity: 'error'
    });
  };

  const resetLocalScan = () => {
    lastIdRef.current = 0;
    startTimeRef.current = null;
    setEvents([]);
    setCurrentTool(null);
    setDone(false);
    setScanStarted(false);
    setElapsedMs(0);
    setHostFilter('all');
    setStats((prev) => ({
      ...prev,
      scan_status: 'idle',
      findings: 0,
      input_tokens: 0,
      output_tokens: 0,
      cost_usd: 0,
      provider: ''
    }));
    setSseKey((k) => k + 1);
  };

  const launchPayload = () => {
    const payload = {};
    const brief = operatorBrief.trim();
    if (brief) payload.operator_brief = brief;
    if (maxTurns.trim()) {
      const turns = Number(maxTurns);
      if (Number.isFinite(turns)) payload.max_turns = turns;
    }
    if (skipPorts) payload.skip_port_discovery = true;
    return payload;
  };

  const handleLaunch = async () => {
    setBusy(true);
    try {
      await launchWaveScan(appId, waveId, launchPayload());
      setDone(false);
      setScanStarted(true);
      setStats((prev) => ({ ...prev, scan_status: 'running' }));
      startTimeRef.current = Date.now();
      setSseKey((k) => k + 1);
      await loadWave();
      setToast({ open: true, message: 'Wave scan launched.', severity: 'success' });
    } catch (error) {
      failWith(error, 'Failed to launch scan.');
    } finally {
      setBusy(false);
    }
  };

  const handleRestart = async () => {
    setBusy(true);
    try {
      await resetWaveScan(appId, waveId);
      resetLocalScan();
      await launchWaveScan(appId, waveId, launchPayload());
      setDone(false);
      setScanStarted(true);
      setStats((prev) => ({ ...prev, scan_status: 'running' }));
      startTimeRef.current = Date.now();
      setSseKey((k) => k + 1);
      await loadWave();
      setToast({ open: true, message: 'Scan restarted with current notes.', severity: 'success' });
    } catch (error) {
      failWith(error, 'Failed to restart scan.');
    } finally {
      setBusy(false);
    }
  };

  const handleStop = async () => {
    setBusy(true);
    try {
      await stopWaveScan(appId, waveId);
      setStats((prev) => ({ ...prev, scan_status: 'stopped' }));
      setCurrentTool(null);
      setDone(true);
      await loadWave();
      setToast({ open: true, message: 'Scan stop requested.', severity: 'success' });
    } catch (error) {
      failWith(error, 'Failed to stop scan.');
    } finally {
      setBusy(false);
    }
  };

  const status = stats.scan_status || 'idle';
  const running = status === 'running';
  const finished = status === 'completed' || status === 'failed' || status === 'stopped';
  const idle = !running && !finished;
  const isOpen = wave?.status === 'open';
  const isStarted = Boolean(wave?.started_at || wave?.started);
  const canLaunch = isOpen && isStarted;
  const waveTo = `/apps/${appId}/waves/${waveId}`;
  const elapsedStr = (() => {
    const s = Math.floor(elapsedMs / 1000);
    const m = Math.floor(s / 60);
    return m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
  })();
  const showCost = Number(stats.cost_usd) > 0;
  const feedRows = useMemo(() => foldEvents(events), [events]);
  const visibleRows = useMemo(() => {
    if (hostFilter === 'all') return feedRows;
    const wanted = Number(hostFilter);
    return feedRows.filter((row) => row.kind === 'phase' || row.kind === 'outcome' || Number(row.recordId) === wanted);
  }, [feedRows, hostFilter]);

  const hostName = (recordId) => {
    const host = hostById.get(Number(recordId));
    return shortHost(host?.name) || (recordId ? `#${recordId}` : '');
  };

  const rowSeverity = (row) => {
    if (row.kind === 'finding') return 'critical';
    if (row.error || (row.kind === 'outcome' && status === 'failed')) return 'high';
    if (row.kind === 'tool' && row.source === 'kali') return 'medium';
    if (row.kind === 'tool') return 'low';
    return 'none';
  };

  const launchForm = canLaunch && (idle || finished) ? (
    <Surface
      style={{
        maxWidth: 720,
        margin: `0 auto ${SPACE.x24}px`,
        padding: SPACE.x16
      }}
    >
      <Text variant="h2" style={{ marginBottom: SPACE.x8 }}>
        {finished ? 'Restart with notes' : 'Launch options'}
      </Text>
      <Text variant="meta" tone="secondary" style={{ marginBottom: SPACE.x16, display: 'block' }}>
        Notes go to the agent as extra prompt. Use them for credentials, out-of-scope paths, or what to focus on.
      </Text>
      <Field
        label="Operator notes"
        hint="Optional. The model treats this as engagement context."
        multiline
        minRows={4}
        value={operatorBrief}
        onChange={(event) => setOperatorBrief(event.target.value)}
        placeholder="e.g. Auth is at /login. Do not brute-force. Focus on IDOR on /api/admin."
      />
      <div style={{ display: 'grid', gridTemplateColumns: '160px 1fr', gap: SPACE.x16, marginTop: SPACE.x12 }}>
        <Field
          label="Max turns"
          hint="Blank uses policy default"
          value={maxTurns}
          onChange={(event) => setMaxTurns(event.target.value)}
          placeholder="40"
        />
        <div />
      </div>
      <SwitchRow
        label="Skip port discovery"
        hint="Use open ports already stored on the records."
        checked={skipPorts}
        onChange={setSkipPorts}
      />
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: SPACE.x8 }}>
        {finished ? (
          <Button
            size="small"
            variant="contained"
            startIcon={<RestartAlt sx={{ fontSize: 16 }} />}
            onClick={handleRestart}
            disabled={busy || scopedHosts.length === 0}
          >
            Restart scan
          </Button>
        ) : (
          <Button
            size="small"
            variant="contained"
            startIcon={<SmartToy sx={{ fontSize: 16 }} />}
            onClick={handleLaunch}
            disabled={busy || scopedHosts.length === 0}
          >
            Launch scan
          </Button>
        )}
      </div>
    </Surface>
  ) : null;

  return (
    <Page>
      <PageHeader
        crumbs={[
          { label: 'Applications', to: '/pentest' },
          { label: appName || 'Application', to: `/apps/${appId}` },
          { label: wave?.name || 'Wave', to: waveTo },
          { label: 'AI scan' }
        ]}
        leading={
          <Button size="small" component={RouterLink} to={waveTo} startIcon={<ArrowBack sx={{ fontSize: 16 }} />}>
            Wave
          </Button>
        }
        title="AI scan"
        subtitle={wave?.name || ''}
        meta={
          <>
            <Tag emphasized={running}>{status}</Tag>
            {stats.provider ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                <ProviderMark type={stats.provider} size={14} />
                <Tag>{stats.provider}</Tag>
              </span>
            ) : null}
            {scanStarted ? <Tag>{elapsedStr}</Tag> : null}
          </>
        }
        actions={
          <>
            {canLaunch && running ? (
              <Button
                size="small"
                startIcon={<Stop sx={{ fontSize: 16 }} />}
                onClick={handleStop}
                disabled={busy}
              >
                Stop scan
              </Button>
            ) : null}
            {canLaunch && idle ? (
              <Button
                size="small"
                variant="contained"
                startIcon={<SmartToy sx={{ fontSize: 16 }} />}
                onClick={handleLaunch}
                disabled={busy || scopedHosts.length === 0}
              >
                Launch scan
              </Button>
            ) : null}
            {canLaunch && finished ? (
              <Button
                size="small"
                startIcon={<RestartAlt sx={{ fontSize: 16 }} />}
                onClick={handleRestart}
                disabled={busy || scopedHosts.length === 0}
              >
                Restart scan
              </Button>
            ) : null}
          </>
        }
      />

      {!(idle && events.length === 0) ? (
        <MetricStrip
          items={[
            { label: 'Findings', value: stats.findings },
            { label: 'Tokens in', value: formatTokens(stats.input_tokens) },
            { label: 'Tokens out', value: formatTokens(stats.output_tokens) },
            ...(showCost ? [{ label: 'Est. USD', value: `$${Number(stats.cost_usd).toFixed(2)}` }] : [])
          ]}
        />
      ) : null}

      {scopedHosts.length > 0 ? (
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: SPACE.x8,
            marginBottom: SPACE.x16
          }}
        >
          <HostChip
            active={hostFilter === 'all'}
            color={hostFilter === 'all' ? palette.accent : palette.textSecondary}
            onClick={() => setHostFilter('all')}
          >
            All hosts
          </HostChip>
          {scopedHosts.map((host) => {
            const color = hostColor(palette, host.id);
            const active = String(hostFilter) === String(host.id);
            return (
              <HostChip
                key={host.id}
                active={active}
                color={color}
                onClick={() => setHostFilter(active ? 'all' : String(host.id))}
              >
                {shortHost(host.name) || host.name}
              </HostChip>
            );
          })}
        </div>
      ) : null}

      {currentTool ? (
        <Surface raised style={{ maxWidth: 880, margin: `0 auto ${SPACE.x16}px`, padding: `${SPACE.x12}px ${SPACE.x16}px` }}>
          <Text variant="meta" tone="secondary">
            Running <Mono style={{ fontWeight: 600 }}>{toolLabel(currentTool.name)}</Mono>
            {currentTool.recordId ? (
              <HostChip
                active
                color={hostColor(palette, currentTool.recordId)}
                onClick={() => setHostFilter(String(currentTool.recordId))}
                style={{ marginLeft: 8 }}
              >
                {hostName(currentTool.recordId)}
              </HostChip>
            ) : null}
            {currentTool.source === 'kali' ? <Tag emphasized style={{ marginLeft: 8 }}>Kali</Tag> : null}
          </Text>
          {currentTool.detail ? (
            <Text variant="meta" tone="tertiary" style={{ display: 'block', marginTop: 6 }}>
              {currentTool.detail}
            </Text>
          ) : null}
        </Surface>
      ) : null}

      {launchForm}

      {idle && events.length === 0 && !canLaunch ? (
        <EmptyState
          icon={Monitor}
          title="No scan running"
          hint="Start an open wave before launching an AI scan."
          actions={
            <Button size="small" component={RouterLink} to={waveTo}>
              Open wave
            </Button>
          }
        />
      ) : idle && events.length === 0 ? null : (
        <Surface style={{ maxWidth: 880, margin: '0 auto', overflow: 'hidden' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              padding: `${SPACE.x16}px ${SPACE.x16}px ${SPACE.x12}px`
            }}
          >
            <Text variant="h2">Activity</Text>
            <Text variant="meta" tone="secondary">
              {visibleRows.length} updates
            </Text>
          </div>
          <div ref={feedRef} style={{ height: 560, overflowY: 'auto' }}>
            {visibleRows.length === 0 ? (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                <Text variant="meta" tone="secondary">
                  {events.length === 0 ? 'Waiting…' : 'Nothing for this host yet.'}
                </Text>
              </div>
            ) : (
              <DataList>
                {visibleRows.map((row) => {
                  const color = row.recordId ? hostColor(palette, row.recordId) : null;
                  const label = hostName(row.recordId);
                  return (
                    <DataRow
                      key={row.id}
                      id={row.id}
                      severity={rowSeverity(row)}
                      title={
                        <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                          <Text variant="bodyStrong">{row.title}</Text>
                          {row.kind === 'tool' && row.source === 'kali' ? <Tag>Kali</Tag> : null}
                          {row.pending ? <Tag emphasized>live</Tag> : null}
                          {row.error ? <Tag emphasized>failed</Tag> : null}
                        </span>
                      }
                      meta={
                        <div style={{ marginTop: 4, minWidth: 0 }}>
                          {row.detail ? (
                            <Text
                              variant="meta"
                              tone="secondary"
                              style={{ display: 'block', marginBottom: label ? 6 : 0 }}
                            >
                              {row.detail}
                            </Text>
                          ) : null}
                          {label && color ? (
                            <HostChip active={String(hostFilter) === String(row.recordId)} color={color} onClick={() => setHostFilter(String(row.recordId))}>
                              {label}
                            </HostChip>
                          ) : null}
                        </div>
                      }
                      trailing={
                        <Text variant="meta" tone="tertiary">
                          {formatTs(row.ts)}
                        </Text>
                      }
                    />
                  );
                })}
              </DataList>
            )}
          </div>
        </Surface>
      )}

      <Toast
        open={toast.open}
        message={toast.message}
        severity={toast.severity}
        onClose={() => setToast((prev) => ({ ...prev, open: false }))}
      />
    </Page>
  );
};

const ScanLive = () => {
  const { recordId, appId } = useParams();
  if (recordId && !appId) return <HostScanLiveRedirect />;
  return <WaveScanLive />;
};

export default ScanLive;
