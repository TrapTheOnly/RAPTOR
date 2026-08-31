import { useState } from 'react';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { Alert } from '@mui/material';
import { Button, EmptyState, Mono, Surface, Tag, Text } from '../../design/primitives';
import { SPACE } from '../../design/tokens';
import { acceptBurpEngagement, acceptBurpProposal } from '../app-workspace/services';
import HttpExchange from '../pentest-record/components/HttpExchange';

const collectHits = (kali) => {
  if (Array.isArray(kali?.hits) && kali.hits.length) {
    return kali.hits.filter((hit) => hit?.kind === 'weak_secret' && hit?.detail);
  }
  const suite = Array.isArray(kali?.suite) ? kali.suite : [];
  const hits = [];
  suite.forEach((step) => {
    const blob = `${step?.stdout || ''}\n${step?.stderr || ''}`;
    const long = blob.match(/\[\+\] CORRECT key found:\s*(.+)/i);
    const short = blob.match(/\[\+\] (.+) is the CORRECT key!/i);
    const detail = (long?.[1] || short?.[1] || '').trim();
    if (detail) hits.push({ step: step.step, kind: 'weak_secret', detail });
  });
  return hits;
};

const BurpEngagementPane = ({ appId, waveId, engagement, onAccepted }) => {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const isScanner = engagement?.kind === 'scanner';
  const proposal = engagement?.proposal;
  const kali =
    engagement?.result && typeof engagement.result === 'object'
      ? engagement.result
      : proposal?.result && typeof proposal.result === 'object'
        ? proposal.result
        : {};
  const hits = isScanner ? [] : collectHits(kali);
  const running =
    !isScanner && (['naming', 'pending', 'queued', 'running'].includes(engagement?.status) || !engagement);
  const findingId = proposal?.finding_id;
  const canAcceptJwt = Boolean(proposal) && !findingId && proposal.status !== 'accepted' && hits.length > 0;
  const canAcceptScanner = isScanner && Boolean(proposal) && !findingId && proposal.status !== 'accepted';
  const exchange = String(proposal?.result?.exchange || engagement?.result?.exchange || '');

  const accept = async () => {
    setBusy(true);
    setError('');
    try {
      const response = isScanner
        ? await acceptBurpProposal(appId, waveId, engagement.source_id)
        : await acceptBurpEngagement(appId, waveId, engagement.source_id);
      const filed = response.data?.finding?.id || response.data?.finding_id;
      if (filed) {
        navigate(`/apps/${appId}/findings/${filed}`);
        return;
      }
      onAccepted?.(response.data);
    } catch (err) {
      setError(err.response?.data?.error || 'Could not accept this proposal.');
    } finally {
      setBusy(false);
    }
  };

  if (running) {
    return <EmptyState title="RAPTOR is naming the job…" />;
  }

  if (isScanner) {
    return (
      <div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: SPACE.x16, alignItems: 'center' }}>
          <Tag>{engagement.status}</Tag>
          <Tag>Scanner</Tag>
          {engagement.host ? (
            <Mono>
              {engagement.host}
              {engagement.path || ''}
            </Mono>
          ) : null}
        </div>
        {error ? (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
            {error}
          </Alert>
        ) : null}
        <Surface style={{ padding: SPACE.x16 }}>
          <Text variant="h2" style={{ marginBottom: SPACE.x8 }}>
            {proposal?.title || engagement.title}
          </Text>
          <Text as="p" variant="body" style={{ margin: `0 0 ${SPACE.x16}px` }}>
            {proposal?.description || 'Burp Scanner issue. Accept to file a finding.'}
          </Text>
          {exchange ? <HttpExchange text={exchange} /> : null}
          {findingId ? (
            <Button size="small" component={RouterLink} to={`/apps/${appId}/findings/${findingId}`}>
              Open finding
            </Button>
          ) : canAcceptScanner ? (
            <Button size="small" variant="contained" onClick={accept} disabled={busy}>
              {busy ? 'Filing…' : 'Accept into finding'}
            </Button>
          ) : null}
        </Surface>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: SPACE.x16, alignItems: 'center' }}>
        <Tag>{engagement.status}</Tag>
        <Tag>{engagement.kind === 'jwt' ? 'JWT' : engagement.kind}</Tag>
        {engagement.host ? (
          <Mono>
            {engagement.host}
            {engagement.path || ''}
          </Mono>
        ) : null}
      </div>
      {error ? (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>
          {error}
        </Alert>
      ) : null}
      {findingId || hits.length > 0 ? (
        <Surface style={{ padding: SPACE.x16 }}>
          <Text variant="h2" style={{ marginBottom: SPACE.x8 }}>
            {proposal?.title || engagement.title}
          </Text>
          <Text as="p" variant="body" style={{ margin: `0 0 ${SPACE.x16}px` }}>
            Recovered a weak HMAC secret. File it if it applies to this host.
          </Text>
          {findingId ? (
            <Button size="small" component={RouterLink} to={`/apps/${appId}/findings/${findingId}`}>
              Open finding
            </Button>
          ) : canAcceptJwt ? (
            <Button size="small" variant="contained" onClick={accept} disabled={busy}>
              {busy ? 'Filing…' : 'Accept into finding'}
            </Button>
          ) : null}
        </Surface>
      ) : null}
      {hits.length === 0 && !findingId && engagement.status === 'completed' ? (
        <EmptyState title="No JWT weakness to file" />
      ) : null}
      {hits.length === 0 && engagement.status === 'failed' ? (
        <EmptyState title="Engagement failed" />
      ) : null}
    </div>
  );
};

export default BurpEngagementPane;
