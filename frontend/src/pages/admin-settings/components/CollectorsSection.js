import React, { useCallback, useEffect, useState } from 'react';
import axios from 'axios';
import { Dns as DnsIcon } from '@mui/icons-material';
import {
  Button,
  Combo,
  DataList,
  DataRow,
  EmptyState,
  Field,
  Mono,
  OsMark,
  Panel,
  Progress,
  RefreshButton,
  StatusGlyph,
  Surface,
  Tag,
  Text
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import SectionHeader from './SectionHeader';
import CollectorsTopology from './CollectorsTopology';

const GRAPH_PAGE_SIZE = 12;
const TABLE_PAGE_SIZE = 25;

const MODE_OPTIONS = [
  { value: 'one_sided', label: 'One-sided (airgap)' },
  { value: 'two_sided', label: 'Two-sided (pingable)' }
];

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
  if (!value) return 'never';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
};

const formatRelative = (value) => {
  if (!value) return 'never';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  const delta = Date.now() - parsed.getTime();
  if (delta < 0) return parsed.toLocaleString();
  if (delta < 45000) return 'just now';
  if (delta < 3600000) return `${Math.max(1, Math.round(delta / 60000))}m ago`;
  if (delta < 86400000) return `${Math.max(1, Math.round(delta / 3600000))}h ago`;
  if (delta < 7 * 86400000) return `${Math.max(1, Math.round(delta / 86400000))}d ago`;
  return parsed.toLocaleDateString();
};

const CopyRow = ({ label, value, onCopy }) => (
  <div style={{ marginTop: SPACE.x8 }}>
    {label ? (
      <Text as="div" variant="micro" tone="tertiary">
        {label}
      </Text>
    ) : null}
    <div style={{ display: 'flex', gap: SPACE.x8, alignItems: 'flex-start', marginTop: 4 }}>
      <Mono style={{ wordBreak: 'break-all', flex: 1 }}>{value}</Mono>
      <Button size="small" onClick={() => onCopy(value)}>
        Copy
      </Button>
    </div>
  </div>
);

const AgentRow = ({ agent, pinging, collecting, onEdit, onPing, onCollect, onDelete }) => {
  const [open, setOpen] = useState(false);
  const name = agent.display_name || agent.hostname || agent.id;
  const hostLine = [agent.hostname, agent.last_seen_ip].filter(Boolean).join(' · ');
  const twoSided = agent.mode === 'two_sided';
  const pingBusy = pinging === agent.id;
  const collectBusy = collecting === agent.id;

  return (
    <DataRow
      id={agent.id}
      expanded={open}
      onToggle={() => setOpen((value) => !value)}
      leading={
        <StatusGlyph status={agent.online ? 'unchanged' : 'missing'} label={agent.online ? 'Online' : 'Offline'} />
      }
      title={<Text variant="bodyStrong">{name}</Text>}
      meta={
        hostLine ? (
          <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 2 }}>
            {hostLine}
          </Text>
        ) : null
      }
      trailing={
        <div
          style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8, flexWrap: 'wrap' }}
          onClick={(event) => event.stopPropagation()}
        >
          <Tag>{twoSided ? 'two-sided' : 'one-sided'}</Tag>
          <Tag>{formatInterval(agent.interval_seconds)}</Tag>
          <Button size="small" onClick={() => onEdit(agent)}>
            Edit
          </Button>
          <Button size="small" disabled={!twoSided || pingBusy} onClick={() => onPing(agent)}>
            {pingBusy ? 'Pinging…' : 'Ping'}
          </Button>
          <Button size="small" disabled={collectBusy} onClick={() => onCollect(agent)}>
            {collectBusy ? 'Collecting…' : 'Collect'}
          </Button>
          <Button size="small" onClick={() => onDelete(agent)}>
            Delete
          </Button>
        </div>
      }
    >
      <Text as="div" variant="meta" tone="secondary" title={formatWhen(agent.last_seen_at)}>
        Live {formatRelative(agent.last_seen_at)} · ingest {formatRelative(agent.last_ingest_at)}
      </Text>
      {twoSided && agent.callback_url ? (
        <Mono as="div" tone="secondary" style={{ marginTop: 4 }}>
          {agent.callback_url}
        </Mono>
      ) : null}
    </DataRow>
  );
};

const CollectorsSection = ({ showMessage }) => {
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
    if (!editAgent) return;
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
    if (!deleteTarget) return;
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
    return <Progress deferred />;
  }

  const tablePages = Math.max(1, Math.ceil(total / TABLE_PAGE_SIZE));
  const graphPages = Math.max(1, Math.ceil(graphTotal / GRAPH_PAGE_SIZE));
  const linuxReady = Boolean(downloads['linux-amd64']?.available || downloads['linux-arm64']?.available);
  const windowsReady = Boolean(downloads['windows-amd64.exe']?.available);

  return (
    <div>
      <SectionHeader title="DNS Collectors">
        {version ? <Tag>{`v${version}`}</Tag> : null}
      </SectionHeader>
      <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x16}px` }}>
        Install an agent on each DNS host and enroll it with a token.
      </Text>

      <div style={{ display: 'flex', gap: SPACE.x8, flexWrap: 'wrap', marginBottom: SPACE.x16 }}>
        <Button
          variant="outlined"
          size="small"
          href="/collector/v1/download/linux-amd64"
          disabled={!linuxReady}
          startIcon={<OsMark type="linux" />}
        >
          Linux amd64
        </Button>
        <Button
          variant="outlined"
          size="small"
          href="/collector/v1/download/linux-arm64"
          disabled={!downloads['linux-arm64']?.available}
          startIcon={<OsMark type="linux" />}
        >
          Linux arm64
        </Button>
        <Button
          variant="outlined"
          size="small"
          href="/collector/v1/download/windows-amd64.exe"
          disabled={!windowsReady}
          startIcon={<OsMark type="windows" />}
        >
          Windows exe
        </Button>
        <Button
          variant="outlined"
          size="small"
          href="/collector/v1/download/install.ps1"
          startIcon={<OsMark type="windows" />}
        >
          Windows install.ps1
        </Button>
        <Button
          variant="outlined"
          size="small"
          href="/collector/v1/download/install.sh"
          startIcon={<OsMark type="linux" />}
        >
          Linux install.sh
        </Button>
      </div>

      {!linuxReady && !windowsReady ? (
        <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x16}px` }}>
          Binaries are built into the RAPTOR image. Rebuild with the collector stage, or run{' '}
          <Mono>make collector-dist</Mono> in the repo.
        </Text>
      ) : null}

      <div
        style={{
          display: 'flex',
          gap: SPACE.x12,
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          marginBottom: SPACE.x16
        }}
      >
        <Field
          label="Agent name"
          value={label}
          onChange={(event) => setLabel(event.target.value)}
          placeholder="dc01-dns"
          fullWidth={false}
          style={{ minWidth: 180, flex: '1 1 180px', maxWidth: 280 }}
        />
        <Combo
          label="Contact mode"
          options={MODE_OPTIONS}
          value={mode}
          onChange={(next) => next && setMode(next)}
          disableClearable
          fullWidth={false}
          style={{ minWidth: 180, flex: '1 1 180px', maxWidth: 260 }}
        />
        <Button variant="contained" onClick={handleCreateToken}>
          Create enroll token
        </Button>
        <RefreshButton onClick={fetchPage} />
      </div>

      {enroll ? (
        <Surface style={{ padding: SPACE.x16, marginBottom: SPACE.x16 }}>
          <Text variant="bodyStrong">Bootstrap token (shown once)</Text>
          <CopyRow value={enroll.token} onCopy={handleCopy} />
          <CopyRow label="Linux" value={enroll.install?.linux || enroll.enroll_command} onCopy={handleCopy} />
          <CopyRow label="Windows" value={enroll.install?.windows || ''} onCopy={handleCopy} />
        </Surface>
      ) : null}

      <CollectorsTopology
        agents={graphAgents}
        page={graphPage}
        pageCount={graphPages}
        onPageChange={setGraphPage}
      />

      <div
        style={{
          display: 'flex',
          gap: SPACE.x12,
          alignItems: 'flex-end',
          marginTop: SPACE.x24,
          marginBottom: SPACE.x12
        }}
      >
        <Field
          label="Search agents"
          value={query}
          onChange={(event) => {
            setTablePage(1);
            setGraphPage(1);
            setQuery(event.target.value);
          }}
          fullWidth={false}
          style={{ maxWidth: 320, width: '100%' }}
        />
        <Tag>{`${total} agent${total === 1 ? '' : 's'}`}</Tag>
      </div>

      {agents.length === 0 ? (
        <EmptyState
          icon={DnsIcon}
          title="No collectors enrolled yet"
          hint="Create an enroll token and run setup on a DNS host."
        />
      ) : (
        <DataList>
          {agents.map((agent) => (
            <AgentRow
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
        </DataList>
      )}

      {tablePages > 1 ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: SPACE.x8, marginTop: SPACE.x16 }}>
          <Button size="small" disabled={tablePage <= 1} onClick={() => setTablePage((page) => page - 1)}>
            Previous
          </Button>
          <Mono>
            {tablePage} / {tablePages}
          </Mono>
          <Button
            size="small"
            disabled={tablePage >= tablePages}
            onClick={() => setTablePage((page) => page + 1)}
          >
            Next
          </Button>
        </div>
      ) : null}

      <Panel
        open={Boolean(editAgent)}
        onClose={closeEdit}
        title="Edit agent"
        actions={
          <>
            <Button onClick={closeEdit} variant="outlined">
              Cancel
            </Button>
            <Button variant="contained" onClick={handleSaveEdit} disabled={savingEdit}>
              Save
            </Button>
          </>
        }
      >
        <Text variant="meta" tone="secondary">
          {editAgent?.hostname || editAgent?.id}
        </Text>
        <Field
          label="Display name"
          value={editName}
          onChange={(event) => setEditName(event.target.value)}
        />
        {editAgent?.mode === 'two_sided' ? (
          <Field
            label="Callback URL"
            value={editCallback}
            onChange={(event) => setEditCallback(event.target.value)}
            placeholder="http://10.0.0.5:7444"
          />
        ) : null}
      </Panel>

      <Panel
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        title="Delete collector"
        actions={
          <>
            <Button onClick={() => setDeleteTarget(null)} variant="outlined">
              Cancel
            </Button>
            <Button variant="contained" onClick={handleDelete}>
              Delete
            </Button>
          </>
        }
      >
        <Text variant="body">
          Delete {deleteTarget?.display_name || deleteTarget?.hostname}? The key is invalidated
          immediately. A still-running agent will be refused on the next ingest.
        </Text>
      </Panel>
    </div>
  );
};

export default CollectorsSection;
