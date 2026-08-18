import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Pagination,
  Paper,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  ContentCopy as CopyIcon,
  Delete as DeleteIcon,
  Dns as DnsIcon,
  Download as DownloadIcon,
  Edit as EditIcon,
  Key as KeyIcon,
  PlayArrow as CollectIcon,
  Refresh as RefreshIcon,
  Sensors as PingIcon
} from '@mui/icons-material';
import SectionHeader from './SectionHeader';
import CollectorsTopology from './CollectorsTopology';

const GRAPH_PAGE_SIZE = 12;
const TABLE_PAGE_SIZE = 25;

const formatInterval = (seconds) => {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) {
    return '5 min';
  }
  if (value % 3600 === 0) {
    const hours = value / 3600;
    return `${hours}h`;
  }
  if (value % 60 === 0) {
    return `${value / 60} min`;
  }
  return `${value}s`;
};

const formatWhen = (value) => {
  if (!value) {
    return 'never';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  return parsed.toLocaleString();
};

const formatRelative = (value) => {
  if (!value) {
    return 'never';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return String(value);
  }
  const delta = Date.now() - parsed.getTime();
  if (delta < 0) {
    return parsed.toLocaleString();
  }
  if (delta < 45000) {
    return 'just now';
  }
  if (delta < 3600000) {
    return `${Math.max(1, Math.round(delta / 60000))}m ago`;
  }
  if (delta < 86400000) {
    return `${Math.max(1, Math.round(delta / 3600000))}h ago`;
  }
  if (delta < 7 * 86400000) {
    return `${Math.max(1, Math.round(delta / 86400000))}d ago`;
  }
  return parsed.toLocaleDateString();
};

const AgentCard = ({
  agent,
  pinging,
  collecting,
  onEdit,
  onPing,
  onCollect,
  onDelete
}) => {
  const theme = useTheme();
  const name = agent.display_name || agent.hostname || agent.id;
  const hostLine = [agent.hostname, agent.last_seen_ip].filter(Boolean).join(' · ');
  const twoSided = agent.mode === 'two_sided';
  const statusColor = agent.online ? theme.palette.success.main : theme.palette.warning.main;
  const pingBusy = pinging === agent.id;
  const collectBusy = collecting === agent.id;

  return (
    <Paper
      sx={{
        p: 1.75,
        backgroundColor: 'background.default',
        border: `1px solid ${theme.palette.divider}`,
        '&:hover': {
          borderColor: theme.palette.primary.main,
          backgroundColor: alpha(theme.palette.primary.main, 0.02)
        },
        transition: 'all 0.2s ease-in-out'
      }}
    >
      <Box
        display="flex"
        alignItems="flex-start"
        gap={1.5}
        sx={{ flexDirection: { xs: 'column', sm: 'row' } }}
      >
        <Box display="flex" alignItems="flex-start" gap={1.5} minWidth={0} flex={1}>
          <Avatar
            sx={{
              width: 40,
              height: 40,
              bgcolor: alpha(statusColor, 0.16),
              color: statusColor,
              fontSize: 16,
              fontWeight: 700
            }}
          >
            {(name || '?').charAt(0).toUpperCase()}
          </Avatar>
          <Box minWidth={0} flex={1}>
            <Box display="flex" alignItems="center" gap={0.75} flexWrap="wrap">
              <Typography variant="subtitle1" sx={{ fontWeight: 700, lineHeight: 1.3 }} noWrap>
                {name}
              </Typography>
              <Chip
                size="small"
                label={agent.online ? 'online' : 'offline'}
                sx={{
                  fontWeight: 600,
                  backgroundColor: alpha(statusColor, 0.14),
                  color: statusColor,
                  border: `1px solid ${alpha(statusColor, 0.35)}`
                }}
              />
              <Chip
                size="small"
                variant="outlined"
                label={twoSided ? 'two-sided' : 'one-sided'}
              />
              <Chip size="small" variant="outlined" label={formatInterval(agent.interval_seconds)} />
            </Box>
            {hostLine ? (
              <Typography variant="caption" color="text.secondary" display="block" noWrap>
                {hostLine}
              </Typography>
            ) : null}
            <Typography variant="caption" color="text.secondary" display="block">
              <Tooltip title={formatWhen(agent.last_seen_at)}>
                <Box component="span">Live {formatRelative(agent.last_seen_at)}</Box>
              </Tooltip>
              {' · '}
              <Tooltip title={formatWhen(agent.last_ingest_at)}>
                <Box component="span">ingest {formatRelative(agent.last_ingest_at)}</Box>
              </Tooltip>
            </Typography>
            {twoSided && agent.callback_url ? (
              <Tooltip title={agent.callback_url}>
                <Typography variant="caption" color="text.secondary" display="block" noWrap>
                  {agent.callback_url}
                </Typography>
              </Tooltip>
            ) : null}
          </Box>
        </Box>

        <Box display="flex" alignItems="center" gap={0.25} sx={{ ml: { sm: 'auto' }, flexShrink: 0 }}>
          <Tooltip title="Edit name and callback">
            <IconButton size="small" color="primary" onClick={() => onEdit(agent)}>
              <EditIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={twoSided ? 'Ping' : 'Ping requires two-sided mode'}>
            <span>
              <IconButton
                size="small"
                disabled={!twoSided || pingBusy}
                onClick={() => onPing(agent)}
              >
                {pingBusy ? <CircularProgress size={16} /> : <PingIcon fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Collect now">
            <span>
              <IconButton
                size="small"
                color="primary"
                disabled={collectBusy}
                onClick={() => onCollect(agent)}
              >
                {collectBusy ? <CircularProgress size={16} /> : <CollectIcon fontSize="small" />}
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton size="small" color="error" onClick={() => onDelete(agent)}>
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    </Paper>
  );
};

const CollectorsSection = ({ showMessage }) => {
  const theme = useTheme();
  const [agents, setAgents] = useState([]);
  const [graphAgents, setGraphAgents] = useState([]);
  const [total, setTotal] = useState(0);
  const [graphTotal, setGraphTotal] = useState(0);
  const [version, setVersion] = useState('');
  const [downloads, setDownloads] = useState({});
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [tablePage, setTablePage] = useState(1);
  const [graphPage, setGraphPage] = useState(1);
  const [label, setLabel] = useState('');
  const [mode, setMode] = useState('one_sided');
  const [enroll, setEnroll] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [editAgent, setEditAgent] = useState(null);
  const [editName, setEditName] = useState('');
  const [editCallback, setEditCallback] = useState('');
  const [savingEdit, setSavingEdit] = useState(false);
  const [pinging, setPinging] = useState(null);
  const [collecting, setCollecting] = useState(null);

  const fetchPage = useCallback(async () => {
    try {
      const [tableRes, graphRes] = await Promise.all([
        axios.get('/admin/collectors', {
          params: { limit: TABLE_PAGE_SIZE, offset: (tablePage - 1) * TABLE_PAGE_SIZE, q: query }
        }),
        axios.get('/admin/collectors', {
          params: { limit: GRAPH_PAGE_SIZE, offset: (graphPage - 1) * GRAPH_PAGE_SIZE, q: query }
        })
      ]);
      setAgents(tableRes.data.agents || []);
      setTotal(tableRes.data.total || 0);
      setGraphAgents(graphRes.data.agents || []);
      setGraphTotal(graphRes.data.total || 0);
      setVersion(tableRes.data.version || '');
      setDownloads(tableRes.data.downloads || {});
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to load collectors.');
    } finally {
      setLoading(false);
    }
  }, [graphPage, query, showMessage, tablePage]);

  useEffect(() => {
    fetchPage();
    const timer = setInterval(fetchPage, 8000);
    return () => clearInterval(timer);
  }, [fetchPage]);

  const handleCreateToken = async () => {
    try {
      const res = await axios.post('/admin/collectors/enroll-tokens', { label, mode });
      setEnroll(res.data);
      showMessage('success', 'Enroll token created. Download the agent, then run the install command.');
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to create enroll token.');
    }
  };

  const handleCopy = async (value) => {
    try {
      await navigator.clipboard.writeText(value);
      showMessage('success', 'Copied to clipboard.');
    } catch (err) {
      showMessage('error', 'Could not copy to clipboard.');
    }
  };

  const openEdit = (agent) => {
    setEditAgent(agent);
    setEditName(agent.display_name || '');
    setEditCallback(agent.callback_url || '');
  };

  const closeEdit = () => {
    setEditAgent(null);
    setEditName('');
    setEditCallback('');
  };

  const handleSaveEdit = async () => {
    if (!editAgent) {
      return;
    }
    setSavingEdit(true);
    try {
      const body = { display_name: editName.trim() };
      if (editAgent.mode === 'two_sided') {
        body.callback_url = editCallback.trim();
      }
      await axios.patch(`/admin/collectors/${editAgent.id}`, body);
      showMessage('success', 'Agent updated.');
      closeEdit();
      fetchPage();
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to update agent.');
    } finally {
      setSavingEdit(false);
    }
  };

  const handleCollectNow = async (agent) => {
    setCollecting(agent.id);
    try {
      const res = await axios.post(`/admin/collectors/${agent.id}/collect-now`);
      if (res.data.immediate) {
        showMessage('success', 'Collect started on the agent.');
      } else if (res.data.reason === 'one_sided') {
        showMessage('success', 'Queued. This one-sided agent will collect on its next heartbeat.');
      } else {
        showMessage(
          'success',
          res.data.error
            ? `Queued for next heartbeat (${res.data.error})`
            : 'Queued. The agent will collect on its next heartbeat.'
        );
      }
      fetchPage();
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to request collect.');
    } finally {
      setCollecting(null);
    }
  };

  const handlePing = async (agent) => {
    setPinging(agent.id);
    try {
      const res = await axios.post(`/admin/collectors/${agent.id}/ping`);
      if (res.data.ok) {
        showMessage('success', `Ping ok (${res.data.latency_ms} ms).`);
      } else {
        showMessage('error', res.data.error || 'Ping failed.');
      }
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Ping failed.');
    } finally {
      setPinging(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) {
      return;
    }
    try {
      await axios.delete(`/admin/collectors/${deleteTarget.id}`);
      showMessage('success', `Deleted ${deleteTarget.display_name || deleteTarget.hostname}.`);
      setDeleteTarget(null);
      fetchPage();
    } catch (err) {
      showMessage('error', err.response?.data?.error || 'Failed to delete collector.');
    }
  };

  if (loading) {
    return null;
  }

  const tablePages = Math.max(1, Math.ceil(total / TABLE_PAGE_SIZE));
  const graphPages = Math.max(1, Math.ceil(graphTotal / GRAPH_PAGE_SIZE));
  const linuxReady = Boolean(downloads['linux-amd64']?.available || downloads['linux-arm64']?.available);
  const windowsReady = Boolean(downloads['windows-amd64.exe']?.available);

  return (
    <Stack spacing={3}>
      <Card>
        <CardContent>
          <SectionHeader icon={DnsIcon} title="DNS Collectors" />
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Download the packaged agent from this page. Drop it on the DNS host, run setup once with
            the enroll token, and it will push zones to RAPTOR. One-sided agents (air-gapped) only
            call out; two-sided agents also accept a ping from RAPTOR. Keep
            <code> raptor-collector run </code> running for two-sided health checks.
            {version ? ` Current package: v${version}.` : ''}
          </Typography>

          <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              href="/collector/v1/download/linux-amd64"
              disabled={!linuxReady}
            >
              Linux amd64
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              href="/collector/v1/download/linux-arm64"
              disabled={!downloads['linux-arm64']?.available}
            >
              Linux arm64
            </Button>
            <Button
              variant="outlined"
              startIcon={<DownloadIcon />}
              href="/collector/v1/download/windows-amd64.exe"
              disabled={!windowsReady}
            >
              Windows exe
            </Button>
            <Button variant="outlined" startIcon={<DownloadIcon />} href="/collector/v1/download/install.ps1">
              Windows install.ps1
            </Button>
            <Button variant="outlined" startIcon={<DownloadIcon />} href="/collector/v1/download/install.sh">
              Linux install.sh
            </Button>
          </Stack>
          {!linuxReady && !windowsReady ? (
            <Alert severity="info" sx={{ mb: 2 }}>
              Binaries are built into the RAPTOR image. Rebuild with the collector stage, or run
              <code> make collector-dist </code> in the repo.
            </Alert>
          ) : null}

          <Stack direction="row" spacing={1.5} useFlexGap flexWrap="wrap" sx={{ mb: 2 }}>
            <TextField
              size="small"
              label="Agent name"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
              placeholder="dc01-dns"
              sx={{ minWidth: 180, flex: '1 1 180px', maxWidth: 280 }}
            />
            <FormControl size="small" sx={{ minWidth: 180, flex: '1 1 180px', maxWidth: 260 }}>
              <InputLabel>Contact mode</InputLabel>
              <Select
                label="Contact mode"
                value={mode}
                onChange={(event) => setMode(event.target.value)}
              >
                <MenuItem value="one_sided">One-sided (airgap)</MenuItem>
                <MenuItem value="two_sided">Two-sided (pingable)</MenuItem>
              </Select>
            </FormControl>
            <Button variant="contained" startIcon={<KeyIcon />} onClick={handleCreateToken}>
              Create enroll token
            </Button>
            <Button startIcon={<RefreshIcon />} onClick={fetchPage}>
              Refresh
            </Button>
          </Stack>

          {enroll ? (
            <Alert severity="warning" sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1 }}>
                Bootstrap token (shown once)
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
                <Box component="code" sx={{ fontSize: 13, wordBreak: 'break-all' }}>
                  {enroll.token}
                </Box>
                <IconButton size="small" onClick={() => handleCopy(enroll.token)}>
                  <CopyIcon fontSize="small" />
                </IconButton>
              </Stack>
              <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                Linux
              </Typography>
              <Stack direction="row" spacing={1} alignItems="flex-start" sx={{ mb: 1 }}>
                <Box component="code" sx={{ fontSize: 12, wordBreak: 'break-all' }}>
                  {enroll.install?.linux || enroll.enroll_command}
                </Box>
                <IconButton
                  size="small"
                  onClick={() => handleCopy(enroll.install?.linux || enroll.enroll_command)}
                >
                  <CopyIcon fontSize="small" />
                </IconButton>
              </Stack>
              <Typography variant="caption" display="block" sx={{ mb: 1 }}>
                Windows
              </Typography>
              <Stack direction="row" spacing={1} alignItems="flex-start">
                <Box component="code" sx={{ fontSize: 12, wordBreak: 'break-all' }}>
                  {enroll.install?.windows}
                </Box>
                <IconButton size="small" onClick={() => handleCopy(enroll.install?.windows || '')}>
                  <CopyIcon fontSize="small" />
                </IconButton>
              </Stack>
            </Alert>
          ) : null}

          <CollectorsTopology
            agents={graphAgents}
            page={graphPage}
            pageCount={graphPages}
            onPageChange={setGraphPage}
          />

          <Stack
            direction={{ xs: 'column', sm: 'row' }}
            spacing={1.5}
            alignItems={{ sm: 'center' }}
            sx={{ mt: 3, mb: 1.5 }}
          >
            <TextField
              size="small"
              label="Search agents"
              value={query}
              onChange={(event) => {
                setTablePage(1);
                setGraphPage(1);
                setQuery(event.target.value);
              }}
              sx={{ maxWidth: 320, width: '100%' }}
            />
            <Chip
              label={`${total} agent${total === 1 ? '' : 's'}`}
              size="small"
              sx={{
                backgroundColor: alpha(theme.palette.info.main, 0.1),
                color: theme.palette.info.main
              }}
            />
          </Stack>

          {agents.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <DnsIcon sx={{ fontSize: 56, color: 'text.secondary', mb: 1 }} />
              <Typography variant="h6" color="text.secondary" gutterBottom>
                No collectors enrolled yet
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Create an enroll token and run setup on a DNS host.
              </Typography>
            </Box>
          ) : (
            <Stack spacing={1.25}>
              {agents.map((agent) => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  pinging={pinging}
                  collecting={collecting}
                  onEdit={openEdit}
                  onPing={handlePing}
                  onCollect={handleCollectNow}
                  onDelete={setDeleteTarget}
                />
              ))}
            </Stack>
          )}
          {tablePages > 1 ? (
            <Pagination
              sx={{ mt: 2 }}
              count={tablePages}
              page={tablePage}
              onChange={(_, value) => setTablePage(value)}
            />
          ) : null}
        </CardContent>
      </Card>

      <Dialog
        open={Boolean(editAgent)}
        onClose={closeEdit}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 2.5,
            border: `1px solid ${theme.palette.divider}`,
            backgroundColor: theme.palette.background.paper
          }
        }}
      >
        <DialogTitle sx={{ borderBottom: `1px solid ${theme.palette.divider}` }}>
          <Box display="flex" alignItems="center" gap={1.25}>
            <Box
              sx={{
                width: 34,
                height: 34,
                borderRadius: 1.5,
                backgroundColor: alpha(theme.palette.primary.main, 0.12),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
            >
              <EditIcon sx={{ color: theme.palette.primary.main, fontSize: 20 }} />
            </Box>
            <Box>
              <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
                Edit agent
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {editAgent?.hostname || editAgent?.id}
              </Typography>
            </Box>
          </Box>
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 2 }}>
            <TextField
              size="small"
              label="Display name"
              value={editName}
              onChange={(event) => setEditName(event.target.value)}
              fullWidth
            />
            {editAgent?.mode === 'two_sided' ? (
              <TextField
                size="small"
                label="Callback URL"
                value={editCallback}
                onChange={(event) => setEditCallback(event.target.value)}
                placeholder="http://10.0.0.5:7444"
                fullWidth
              />
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={closeEdit}>Cancel</Button>
          <Button variant="contained" onClick={handleSaveEdit} disabled={savingEdit}>
            Save
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(deleteTarget)} onClose={() => setDeleteTarget(null)}>
        <DialogTitle>Delete collector</DialogTitle>
        <DialogContent>
          Delete {deleteTarget?.display_name || deleteTarget?.hostname}? The key is invalidated
          immediately. A still-running agent will be refused on the next ingest.
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleDelete}>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
};

export default CollectorsSection;
