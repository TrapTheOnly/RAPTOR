import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert } from '@mui/material';
import { Button, DataList, DataRow, EmptyState, Mono, Surface, Tag, Text } from '../../design/primitives';
import { SPACE } from '../../design/tokens';
import { fileBurpEvidence, proposeBurpScanner } from '../app-workspace/services';
import HttpExchange from '../pentest-record/components/HttpExchange';

const statusLine = (statuses) => {
  const entries = Object.entries(statuses || {});
  if (!entries.length) return '';
  return entries.map(([code, count]) => `${code}×${count}`).join(' · ');
};

const TOOL_FLAGS = new Set(['intruder', 'repeater', 'scanner', 'proxy']);

const clusterTags = (row) => {
  const tags = [...(row.deltas || [])];
  (row.flags || []).forEach((flag) => {
    if (TOOL_FLAGS.has(flag)) return;
    if (flag === '5xx' && tags.includes('5xx')) return;
    if (flag === 'auth' && tags.some((item) => item.includes('401') || item.includes('403'))) return;
    if (!tags.includes(flag)) tags.push(flag);
  });
  return tags;
};

const toolLabel = (tool) => {
  const value = String(tool || '').trim();
  if (!value) return '';
  return value.charAt(0).toUpperCase() + value.slice(1);
};

const clusterKey = (row) => `${row.tool || 'repeater'}:${row.method}:${row.host}:${row.path}`;

const AnalyzeEngagementPane = ({ appId, waveId, engagement, onFiled, onProposed }) => {
  const navigate = useNavigate();
  const [openKey, setOpenKey] = useState('');
  const [busyKey, setBusyKey] = useState('');
  const [error, setError] = useState('');
  const running = ['naming', 'pending', 'queued', 'running'].includes(engagement?.status) || !engagement;
  const result = engagement?.result && typeof engagement.result === 'object' ? engagement.result : {};
  const clusters = Array.isArray(result.clusters) ? result.clusters : [];
  const narrative = String(result.narrative || '').trim();

  const act = async (key, task) => {
    setBusyKey(key);
    setError('');
    try {
      await task();
    } catch (err) {
      setError(err.response?.data?.error || 'Could not file that traffic.');
    } finally {
      setBusyKey('');
    }
  };

  const fileEvidence = (row) => {
    const eventId = row?.best?.id;
    if (!eventId) return;
    act(`${clusterKey(row)}:file`, async () => {
      const response = await fileBurpEvidence(appId, waveId, { event_id: eventId });
      const filed = response.data?.finding_id || response.data?.finding?.id;
      onFiled?.(response.data);
      if (filed) {
        navigate(`/apps/${appId}/findings/${filed}`);
      }
    });
  };

  const propose = (row) => {
    const eventId = row?.scanner_event_id || row?.best?.id;
    if (!eventId) return;
    act(`${clusterKey(row)}:propose`, async () => {
      const response = await proposeBurpScanner(appId, waveId, { event_id: eventId });
      onProposed?.(response.data?.engagement_id);
    });
  };

  if (running) {
    return <EmptyState title="RAPTOR is naming the job…" />;
  }

  if (engagement.status === 'failed') {
    return <EmptyState title="Engagement failed" hint={engagement.error || ''} />;
  }

  if (clusters.length === 0) {
    return <EmptyState title="No Burp traffic to summarize" />;
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: SPACE.x16, alignItems: 'center' }}>
        <Tag>{engagement.status}</Tag>
        <Tag>Analyze</Tag>
        <Tag>{`${clusters.length} cluster${clusters.length === 1 ? '' : 's'}`}</Tag>
        <Tag>{`${result.send_count || 0} sends`}</Tag>
      </div>
      {error ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      ) : null}
      {narrative ? (
        <Surface style={{ padding: SPACE.x16, marginBottom: SPACE.x16 }}>
          <Text as="p" variant="body" style={{ margin: 0 }}>
            {narrative}
          </Text>
        </Surface>
      ) : null}
      <Surface style={{ overflow: 'hidden' }}>
        <div style={{ padding: `${SPACE.x16}px ${SPACE.x16}px ${SPACE.x8}px` }}>
          <Text variant="h2">What you tried</Text>
        </div>
        <DataList>
          {clusters.map((row) => {
            const key = clusterKey(row);
            const expanded = openKey === key;
            const tags = clusterTags(row);
            const jwtSeen = Boolean(row.jwt_present) || tags.includes('jwt');
            const isScanner = Boolean(row.scanner_name) || (row.flags || []).includes('scanner');
            const busy = busyKey.startsWith(key);
            return (
              <DataRow
                key={key}
                id={key}
                expanded={expanded}
                onToggle={() => setOpenKey(expanded ? '' : key)}
                title={
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <Text variant="bodyStrong">
                      {row.method} {row.path}
                    </Text>
                    {toolLabel(row.tool) ? <Tag>{toolLabel(row.tool)}</Tag> : null}
                    {tags.map((flag) => (
                      <Tag key={flag} emphasized={flag === '5xx' || String(flag).includes('→')}>
                        {flag}
                      </Tag>
                    ))}
                  </span>
                }
                meta={
                  <div style={{ marginTop: 4 }}>
                    <Text variant="meta" tone="secondary" style={{ display: 'block' }}>
                      <Mono>{row.host}</Mono>
                      {` · ${row.count} send${row.count === 1 ? '' : 's'}`}
                      {statusLine(row.statuses) ? ` · ${statusLine(row.statuses)}` : ''}
                    </Text>
                  </div>
                }
              >
                {row.best?.exchange ? <HttpExchange text={row.best.exchange} /> : null}
                {row.payload ? (
                  <Text variant="meta" tone="secondary" style={{ display: 'block', marginBottom: SPACE.x8 }}>
                    Payload <Mono>{row.payload}</Mono>
                  </Text>
                ) : null}
                {jwtSeen ? (
                  <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x8}px` }}>
                    JWT seen — Send JWT from Burp. RAPTOR does not store tokens.
                  </Text>
                ) : null}
                {row.scanner_name ? (
                  <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x8}px` }}>
                    {row.scanner_name}
                    {row.scanner_severity ? ` · ${row.scanner_severity}` : ''}
                  </Text>
                ) : null}
                {row.best?.id ? (
                  <Text as="p" variant="meta" tone="secondary" style={{ margin: `0 0 ${SPACE.x8}px` }}>
                    Attach HTTP copies this exchange onto a draft finding. RAPTOR does not treat a 200 as
                    an incident — you decide what is proof.
                  </Text>
                ) : null}
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {row.best?.id ? (
                    <Button size="small" onClick={() => fileEvidence(row)} disabled={busy}>
                      {busyKey === `${key}:file` ? 'Attaching…' : 'Attach HTTP to a draft'}
                    </Button>
                  ) : null}
                  {isScanner && (row.scanner_event_id || row.best?.id) ? (
                    <Button size="small" variant="contained" onClick={() => propose(row)} disabled={busy}>
                      {busyKey === `${key}:propose` ? 'Proposing…' : 'Propose'}
                    </Button>
                  ) : null}
                </div>
              </DataRow>
            );
          })}
        </DataList>
      </Surface>
    </div>
  );
};

export default AnalyzeEngagementPane;
