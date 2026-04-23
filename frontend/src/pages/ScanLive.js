import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  LinearProgress,
  Stack,
  Typography,
  alpha,
} from '@mui/material';
import {
  ArrowBack as ArrowBackIcon,
  BugReport as BugIcon,
  CheckCircle as CheckCircleIcon,
  Code as CodeIcon,
  Error as ErrorIcon,
  Psychology as BrainIcon,
  Security as SecurityIcon,
  Terminal as TerminalIcon,
} from '@mui/icons-material';
import { useTheme } from '@mui/material/styles';
import axios from 'axios';

const MAX_FEED_EVENTS = 200;

const SOURCE_COLORS = {
  kali: 'error',
  raptor: 'primary',
  unknown: 'default',
};

const SOURCE_LABELS = {
  kali: 'Kali',
  raptor: 'RAPTOR',
  unknown: '?',
};

const EVENT_ICONS = {
  api_call: <BrainIcon fontSize="small" />,
  tool_call: <TerminalIcon fontSize="small" />,
  tool_result: <CodeIcon fontSize="small" />,
  finding: <BugIcon fontSize="small" />,
  status: <SecurityIcon fontSize="small" />,
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

function StatusBadge({ status }) {
  const map = {
    running: { color: 'info', label: 'Running', icon: <CircularProgress size={12} color="inherit" /> },
    completed: { color: 'success', label: 'Completed', icon: <CheckCircleIcon fontSize="small" /> },
    failed: { color: 'error', label: 'Failed', icon: <ErrorIcon fontSize="small" /> },
    idle: { color: 'default', label: 'Idle', icon: null },
  };
  const cfg = map[status] || map.idle;
  return (
    <Chip
      size="small"
      color={cfg.color}
      icon={cfg.icon}
      label={cfg.label}
      variant={status === 'running' ? 'filled' : 'outlined'}
    />
  );
}

function StatCard({ label, value, color }) {
  const theme = useTheme();
  return (
    <Box
      sx={{
        px: 2,
        py: 1.5,
        borderRadius: 2,
        border: `1px solid ${theme.palette.divider}`,
        minWidth: 100,
        textAlign: 'center',
        bgcolor: color ? alpha(theme.palette[color]?.main || theme.palette.primary.main, 0.07) : 'background.paper',
      }}
    >
      <Typography variant="h5" fontWeight={700} color={color ? `${color}.main` : 'text.primary'}>
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

function FeedEvent({ event }) {
  const theme = useTheme();
  const { event_type, payload, ts } = event;

  let primary = event_type;
  let secondary = '';
  let chipColor = 'default';
  let chipLabel = null;
  let isError = false;

  if (event_type === 'tool_call') {
    primary = payload.tool_name || 'unknown';
    secondary = payload.input_snippet || '';
    chipColor = SOURCE_COLORS[payload.mcp_source] || 'default';
    chipLabel = SOURCE_LABELS[payload.mcp_source] || payload.mcp_source;
  } else if (event_type === 'tool_result') {
    primary = payload.tool_name || 'unknown';
    secondary = payload.result_snippet || '';
    isError = !!payload.is_error;
    chipColor = SOURCE_COLORS[payload.mcp_source] || 'default';
    chipLabel = SOURCE_LABELS[payload.mcp_source] || payload.mcp_source;
  } else if (event_type === 'api_call') {
    primary = `API call #${payload.api_call_count}`;
    secondary = `+${payload.input_tokens}in / +${payload.output_tokens}out  •  $${(payload.cost_usd || 0).toFixed(4)}`;
    chipLabel = 'Bedrock';
    chipColor = 'secondary';
  } else if (event_type === 'finding') {
    primary = `Finding #${payload.findings_count}`;
    chipLabel = 'vuln';
    chipColor = 'error';
  } else if (event_type === 'status') {
    primary = `Status → ${payload.scan_status}`;
    if (payload.reason) secondary = payload.reason;
    chipLabel = payload.scan_status;
    chipColor = payload.scan_status === 'completed' ? 'success' : payload.scan_status === 'failed' ? 'error' : 'info';
  }

  return (
    <Box
      sx={{
        display: 'flex',
        gap: 1.5,
        alignItems: 'flex-start',
        py: 0.75,
        px: 1,
        borderRadius: 1,
        bgcolor: isError ? alpha(theme.palette.error.main, 0.06) : 'transparent',
        '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.04) },
      }}
    >
      <Box sx={{ pt: 0.25, color: isError ? 'error.main' : 'text.secondary', flexShrink: 0 }}>
        {EVENT_ICONS[event_type] || <CodeIcon fontSize="small" />}
      </Box>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
          <Typography variant="body2" fontWeight={600} sx={{ fontFamily: 'monospace' }}>
            {primary}
          </Typography>
          {chipLabel && (
            <Chip size="small" label={chipLabel} color={chipColor} variant="outlined"
              sx={{ height: 18, fontSize: 10, '& .MuiChip-label': { px: 0.75 } }} />
          )}
          <Typography variant="caption" color="text.disabled" sx={{ ml: 'auto', flexShrink: 0 }}>
            {formatTs(ts)}
          </Typography>
        </Box>
        {secondary && (
          <Typography variant="caption" color={isError ? 'error.main' : 'text.secondary'}
            sx={{ display: 'block', fontFamily: 'monospace', mt: 0.25, wordBreak: 'break-all' }}>
            {secondary}
          </Typography>
        )}
      </Box>
    </Box>
  );
}

const ScanLive = ({ darkMode }) => {
  const { recordId } = useParams();
  const navigate = useNavigate();
  const theme = useTheme();

  const [record, setRecord] = useState(null);
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState({
    scan_status: 'idle',
    api_calls: 0,
    raptor_calls: 0,
    kali_calls: 0,
    findings: 0,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    cost_limit_usd: 0,
  });
  const [currentTool, setCurrentTool] = useState(null);
  const [done, setDone] = useState(false);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [scanStarted, setScanStarted] = useState(false);
  const startTimeRef = useRef(null);
  const feedRef = useRef(null);
  const eventSourceRef = useRef(null);
  const lastIdRef = useRef(0);

  useEffect(() => {
    axios.get(`/pentest/records`).then((res) => {
      const pentests = Array.isArray(res.data) ? res.data : (res.data?.pentests || []);
      const found = pentests.find(
        (p) => String(p.record_id) === String(recordId) || String(p.id) === String(recordId)
      ) || null;
      if (found) setRecord(found);
    }).catch(() => {});
  }, [recordId]);

  const applyEvent = useCallback((ev) => {
    const { event_type, payload, ts, id } = ev;
    lastIdRef.current = id;

    setEvents((prev) => {
      const next = [...prev, ev];
      return next.length > MAX_FEED_EVENTS ? next.slice(next.length - MAX_FEED_EVENTS) : next;
    });

    if (event_type === 'status') {
      const status = payload.scan_status;
      setStats((s) => ({
        ...s,
        scan_status: status,
        findings: payload.findings_count ?? s.findings,
        input_tokens: payload.input_tokens ?? s.input_tokens,
        output_tokens: payload.output_tokens ?? s.output_tokens,
        cost_usd: payload.cost_usd ?? s.cost_usd,
      }));
      if (status === 'running' && !startTimeRef.current) {
        const eventTimeMs = toEpochMs(ts);
        startTimeRef.current = eventTimeMs || Date.now();
        setElapsedMs(Math.max(0, Date.now() - startTimeRef.current));
        setScanStarted(true);
      }
      if (status === 'completed' || status === 'failed') {
        setCurrentTool(null);
        setDone(true);
      }
    } else if (event_type === 'api_call') {
      setStats((s) => ({
        ...s,
        api_calls: payload.api_call_count ?? s.api_calls + 1,
        input_tokens: payload.total_input_tokens ?? s.input_tokens,
        output_tokens: payload.total_output_tokens ?? s.output_tokens,
        cost_usd: payload.cost_usd ?? s.cost_usd,
        cost_limit_usd: payload.cost_limit_usd || s.cost_limit_usd,
      }));
    } else if (event_type === 'tool_call') {
      setCurrentTool({ name: payload.tool_name, source: payload.mcp_source });
      if (payload.mcp_source === 'kali') {
        setStats((s) => ({ ...s, kali_calls: s.kali_calls + 1 }));
      } else if (payload.mcp_source === 'raptor') {
        setStats((s) => ({ ...s, raptor_calls: s.raptor_calls + 1 }));
      }
    } else if (event_type === 'tool_result') {
      setCurrentTool(null);
    } else if (event_type === 'finding') {
      setStats((s) => ({ ...s, findings: payload.findings_count ?? s.findings + 1 }));
    }
  }, []);

  const [sseKey, setSseKey] = useState(0);

  useEffect(() => {
    if (done) return;
    const url = `/pentest/${recordId}/scan-events/stream?after=${lastIdRef.current}`;
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.__done__) { setDone(true); es.close(); return; }
        applyEvent(data);
      } catch {}
    };
    es.onerror = () => {
      es.close();
      if (!done) setTimeout(() => setSseKey((k) => k + 1), 3000);
    };
    return () => es.close();
  }, [recordId, done, applyEvent, sseKey]);

  useEffect(() => {
    if (done || !scanStarted) return;
    const iv = setInterval(() => setElapsedMs(Date.now() - (startTimeRef.current || Date.now())), 500);
    return () => clearInterval(iv);
  }, [done, scanStarted]);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [events]);

  const elapsedStr = () => {
    const s = Math.floor(elapsedMs / 1000);
    const m = Math.floor(s / 60);
    return m > 0 ? `${m}m ${s % 60}s` : `${s}s`;
  };

  const costPct = stats.cost_limit_usd > 0 ? Math.min((stats.cost_usd / stats.cost_limit_usd) * 100, 100) : 0;

  return (
    <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1100, mx: 'auto' }}>
      {/* Header */}
      <Card sx={{ mb: 2, border: `1px solid ${theme.palette.divider}`,
        background: `linear-gradient(120deg, ${alpha(theme.palette.primary.main, 0.12)} 0%, ${alpha(theme.palette.background.paper, 0.94)} 60%)` }}>
        <CardContent>
          <Box display="flex" justifyContent="space-between" alignItems="flex-start" flexWrap="wrap" gap={2}>
            <Box>
              <Stack direction="row" spacing={1} alignItems="center" mb={0.5}>
                <BrainIcon color="primary" />
                <Typography variant="h5" fontWeight={700}>
                  AI Scan — Live Progress
                </Typography>
                <StatusBadge status={stats.scan_status} />
              </Stack>
              {record && (
                <Typography variant="body2" color="text.secondary">
                  {record.dns_name || record.ip_address || `Record #${recordId}`}
                  {record.ip_address && record.dns_name ? ` · ${record.ip_address}` : ''}
                </Typography>
              )}
            </Box>
            <Stack direction="row" spacing={1} alignItems="center">
              {scanStarted && !done && (
                <Chip size="small" label={`Elapsed: ${elapsedStr()}`} variant="outlined" />
              )}
              <Chip
                size="small"
                label={`Back to record`}
                icon={<ArrowBackIcon fontSize="small" />}
                onClick={() => navigate(`/pentest/record/${recordId}`)}
                sx={{ cursor: 'pointer' }}
                variant="outlined"
              />
            </Stack>
          </Box>

          {/* Cost bar */}
          {stats.cost_limit_usd > 0 && (
            <Box mt={1.5}>
              <Box display="flex" justifyContent="space-between" mb={0.5}>
                <Typography variant="caption" color="text.secondary">Cost</Typography>
                <Typography variant="caption" fontFamily="monospace">
                  ${stats.cost_usd.toFixed(4)} / ${stats.cost_limit_usd.toFixed(2)}
                </Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={costPct}
                color={costPct > 80 ? 'error' : costPct > 50 ? 'warning' : 'primary'}
                sx={{ height: 6, borderRadius: 3 }}
              />
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Stats row */}
      <Stack direction="row" spacing={1.5} flexWrap="wrap" useFlexGap mb={2}>
        <StatCard label="API calls" value={stats.api_calls} />
        <StatCard label="RAPTOR calls" value={stats.raptor_calls} color="primary" />
        <StatCard label="Kali calls" value={stats.kali_calls} color="error" />
        <StatCard label="Findings" value={stats.findings} color={stats.findings > 0 ? 'error' : undefined} />
        <StatCard label="Tokens in" value={stats.input_tokens.toLocaleString()} />
        <StatCard label="Tokens out" value={stats.output_tokens.toLocaleString()} />
      </Stack>

      {/* Current tool */}
      {currentTool && (
        <Card sx={{ mb: 2, border: `1px solid ${theme.palette.info.main}`,
          bgcolor: alpha(theme.palette.info.main, 0.06) }}>
          <CardContent sx={{ py: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Stack direction="row" spacing={1} alignItems="center">
              <CircularProgress size={16} color="info" />
              <Typography variant="body2" fontWeight={600}>Running:</Typography>
              <Typography variant="body2" fontFamily="monospace">{currentTool.name}</Typography>
              <Chip size="small" label={SOURCE_LABELS[currentTool.source] || currentTool.source}
                color={SOURCE_COLORS[currentTool.source] || 'default'} variant="outlined"
                sx={{ height: 18, fontSize: 10, '& .MuiChip-label': { px: 0.75 } }} />
            </Stack>
          </CardContent>
        </Card>
      )}

      {/* Event feed */}
      <Card sx={{ border: `1px solid ${theme.palette.divider}` }}>
        <CardContent sx={{ pb: '12px !important' }}>
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
            <Typography variant="subtitle2" fontWeight={600}>Event Feed</Typography>
            <Typography variant="caption" color="text.secondary">{events.length} events</Typography>
          </Box>
          <Divider sx={{ mb: 1 }} />
          <Box
            ref={feedRef}
            sx={{
              height: 480,
              overflowY: 'auto',
              '&::-webkit-scrollbar': { width: 4 },
              '&::-webkit-scrollbar-thumb': { bgcolor: 'divider', borderRadius: 2 },
            }}
          >
            {events.length === 0 ? (
              <Box display="flex" alignItems="center" justifyContent="center" height="100%">
                <Stack alignItems="center" spacing={1}>
                  <CircularProgress size={28} />
                  <Typography variant="body2" color="text.secondary">
                    Waiting for scan events…
                  </Typography>
                </Stack>
              </Box>
            ) : (
              events.map((ev, i) => (
                <React.Fragment key={ev.id ?? i}>
                  <FeedEvent event={ev} />
                  {i < events.length - 1 && <Divider sx={{ opacity: 0.4 }} />}
                </React.Fragment>
              ))
            )}
          </Box>
        </CardContent>
      </Card>

      {done && (
        <Alert severity={stats.scan_status === 'completed' ? 'success' : 'error'} sx={{ mt: 2 }}>
          Scan {stats.scan_status}.{' '}
          {stats.scan_status === 'completed' && `${stats.findings} finding(s) recorded.`}
        </Alert>
      )}
    </Box>
  );
};

export default ScanLive;
