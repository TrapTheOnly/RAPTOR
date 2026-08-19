import React, { useState } from 'react';
import { Checkbox } from '@mui/material';
import { Link as RouterLink, useNavigate } from 'react-router-dom';
import { ArrowBack, DeleteOutline, Flag, Monitor, RestartAlt, SmartToy } from '@mui/icons-material';
import {
  Button,
  Combo,
  DataList,
  DataRow,
  EmptyState,
  EnvTag,
  Mono,
  Page,
  PageHeader,
  Panel,
  Tag,
  Tabs,
  Text,
  Toolbar
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import FindingCard from './FindingCard';

const formatDate = (value) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

const WaveDetailTab = ({
  appId,
  appName,
  wave,
  environments = [],
  hosts = [],
  findings = [],
  members = [],
  pentestUsers = [],
  canModify,
  canExport,
  canCreateFinding,
  canDelete,
  busyFinding,
  onEndWave,
  onStartWave,
  onDeleteWave,
  onOccurrenceStatusChange,
  onOpenTicket,
  onOpenMerge,
  onPromote,
  onAttachHosts,
  onCreateFinding,
  onSaveMembers,
  onSaveEnvironments,
  username = '',
  onClaimHost,
  onSetHostScope,
  canLaunchScan,
  onLaunchScan,
  onRestartScan,
  scanBusyId
}) => {
  const navigate = useNavigate();
  const [section, setSection] = useState('overview');
  const [memberDraft, setMemberDraft] = useState(null);
  const [envDraft, setEnvDraft] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [deleting, setDeleting] = useState(false);

  if (!wave) {
    return (
      <Page>
        <EmptyState icon={Flag} title="Wave not found" hint="This engagement is missing or belongs to another application." />
      </Page>
    );
  }

  const isOpen = wave.status === 'open';
  const isStarted = Boolean(wave.started_at || wave.started);
  const statusLabel = !isOpen ? 'ended' : isStarted ? 'in progress' : 'not started';
  const currentMembers = memberDraft || members;
  const currentEnvIds = (envDraft
    || (wave.env_ids?.length ? wave.env_ids : wave.environment_id ? [wave.environment_id] : [])
  )
    .map((id) => Number(id))
    .filter((id) => Number.isFinite(id));
  const waveEnvs = environments.filter((env) => currentEnvIds.map(String).includes(String(env.id)));
  const envOptions = environments
    .filter((env) => env.slug !== 'unassigned')
    .map((env) => ({
      value: Number(env.id),
      label: `${env.display_name} (${env.slug})`
    }));
  const userOptions = [...new Set([...(pentestUsers || []), ...currentMembers, wave.opened_by].filter(Boolean))].map(
    (name) => ({ value: name, label: name })
  );
  const backToWaves = () => navigate(`/apps/${appId}`, { state: { tab: 'waves' } });
  const isWaveTester = currentMembers.includes(username) || wave.opened_by === username;
  const selectedHosts = hosts.filter((host) => selectedIds.includes(host.id));
  const allInScope = selectedHosts.length > 0 && selectedHosts.every((host) => host.in_scope !== false);
  const allOutOfScope = selectedHosts.length > 0 && selectedHosts.every((host) => host.in_scope === false);

  const toggle = (id) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));
  const allSelected = hosts.length > 0 && selectedIds.length > 0 && hosts.every((host) => selectedIds.includes(host.id));

  const applyScope = async (inScope) => {
    if (!onSetHostScope || !selectedIds.length) return;
    await onSetHostScope({ record_ids: selectedIds, in_scope: inScope });
    setSelectedIds([]);
  };

  return (
    <Page>
      <PageHeader
        crumbs={[
          { label: 'Applications', to: '/pentest' },
          { label: appName || 'Application', to: `/apps/${appId}` },
          { label: 'Waves', to: `/apps/${appId}` },
          { label: wave.name }
        ]}
        leading={
          <Button size="small" startIcon={<ArrowBack sx={{ fontSize: 16 }} />} onClick={backToWaves}>
            Waves
          </Button>
        }
        title={wave.name}
        subtitle="Live hosts from the environments on this wave. New hosts filed into those environments show up immediately."
        meta={
          <>
            <Tag>{statusLabel}</Tag>
            {waveEnvs.map((env) => (
              <EnvTag key={env.id} slug={env.slug} label={env.slug} />
            ))}
            <Tag>{`${hosts.length} hosts`}</Tag>
            <Tag>{`${findings.length} finding${findings.length === 1 ? '' : 's'}`}</Tag>
          </>
        }
        actions={
          <>
            {canCreateFinding && isOpen && isStarted ? (
              <Button size="small" variant="outlined" onClick={onCreateFinding}>
                New finding
              </Button>
            ) : null}
            {canModify && isOpen && !isStarted ? (
              <Button size="small" variant="contained" onClick={() => onStartWave(wave.id)}>
                Start wave
              </Button>
            ) : null}
            {canExport && isOpen ? (
              <Button size="small" variant="contained" onClick={() => onEndWave(wave)}>
                End and export
              </Button>
            ) : null}
            {canDelete ? (
              <Button size="small" startIcon={<DeleteOutline />} onClick={() => setDeleting(true)}>
                Delete
              </Button>
            ) : null}
          </>
        }
      />

      <Tabs
        value={section}
        onChange={setSection}
        items={[
          { value: 'overview', label: 'Overview' },
          { value: 'hosts', label: `Hosts (${hosts.length})` },
          { value: 'findings', label: `Findings (${findings.length})` }
        ]}
      />

      {section === 'overview' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x24 }}>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {wave.opened_at ? <Tag>{`opened ${formatDate(wave.opened_at)} by ${wave.opened_by || 'unknown'}`}</Tag> : null}
            {wave.started_at ? <Tag>{`started ${formatDate(wave.started_at)}`}</Tag> : null}
            {wave.closed_at ? <Tag>{`ended ${formatDate(wave.closed_at)}`}</Tag> : null}
          </div>
          {wave.notes ? (
            <Text as="p" variant="meta" tone="secondary" style={{ whiteSpace: 'pre-line', margin: 0 }}>
              {wave.notes}
            </Text>
          ) : null}

          <section>
            <Text as="div" variant="h2" style={{ marginBottom: 8 }}>
              Environments
            </Text>
            <Text as="p" variant="meta" tone="secondary" style={{ margin: '0 0 12px', maxWidth: 560 }}>
              Standing RoE and destructive-tool ceilings live on each environment. Adding an environment to an
              open wave lists every host currently in it, in scope by default.
            </Text>
            <Combo
              label="Environments on this wave"
              multiple
              options={envOptions}
              value={currentEnvIds}
              onChange={(value) => setEnvDraft(value || [])}
              disabled={!canModify || !isOpen}
              placeholder="Add an environment"
            />
            {canModify && isOpen && envDraft ? (
              <div style={{ marginTop: 12 }}>
                <Button
                  size="small"
                  variant="contained"
                  disabled={!envDraft.length}
                  onClick={async () => {
                    await onSaveEnvironments(envDraft);
                    setEnvDraft(null);
                  }}
                >
                  Save environments
                </Button>
              </div>
            ) : null}
            {waveEnvs.length ? (
              <DataList style={{ marginTop: 16 }}>
                {waveEnvs.map((env) => {
                  const count = hosts.filter((host) => String(host.environment_id) === String(env.id)).length;
                  return (
                    <DataRow
                      key={env.id}
                      id={env.id}
                      onToggle={() => navigate(`/apps/${appId}/envs/${env.id}`)}
                      title={<Text variant="bodyStrong">{env.display_name || env.slug}</Text>}
                      meta={
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                          <EnvTag slug={env.slug} label={env.slug} />
                          <Tag>{`${count} live hosts`}</Tag>
                        </div>
                      }
                      trailing={
                        <Button size="small" component={RouterLink} to={`/apps/${appId}/envs/${env.id}`}>
                          Environment
                        </Button>
                      }
                    />
                  );
                })}
              </DataList>
            ) : null}
          </section>

          <section>
            <Text as="div" variant="h2" style={{ marginBottom: 8 }}>
              Testers on this wave
            </Text>
            <Text as="p" variant="meta" tone="secondary" style={{ margin: '0 0 12px', maxWidth: 560 }}>
              Testers listed here collaborate on every live host. Anyone on the wave can take a host from the Hosts
              tab. Findings filed in this wave copy this list too.
            </Text>
            <Combo
              label="Members"
              multiple
              freeSolo
              mode="enum"
              options={userOptions}
              value={currentMembers}
              onChange={(value) => setMemberDraft(value || [])}
              disabled={!canModify}
              placeholder="Add pentest users"
              hint="Save to apply testers to this wave and its hosts."
            />
            {canModify && memberDraft ? (
              <div style={{ marginTop: 12 }}>
                <Button
                  size="small"
                  variant="contained"
                  onClick={async () => {
                    await onSaveMembers(memberDraft);
                    setMemberDraft(null);
                  }}
                >
                  Save members
                </Button>
              </div>
            ) : null}
          </section>
        </div>
      ) : null}

      {section === 'hosts' ? (
        hosts.length === 0 ? (
          <EmptyState
            title="No hosts in these environments"
            hint="File hosts into an environment on the application Hosts tab. They appear here as soon as that environment is on the wave."
          />
        ) : (
          <div>
            {canModify && isOpen ? (
              <Toolbar>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 32 }}>
                  <Checkbox
                    size="small"
                    checked={allSelected}
                    indeterminate={selectedIds.length > 0 && !allSelected}
                    onChange={() => setSelectedIds(allSelected ? [] : hosts.map((host) => host.id))}
                  />
                  <Text variant="meta" tone="secondary">
                    {selectedIds.length > 0 ? `${selectedIds.length} selected` : 'Select hosts'}
                  </Text>
                </div>
                <div style={{ flexGrow: 1 }} />
                <Button
                  size="small"
                  variant="outlined"
                  disabled={selectedIds.length === 0 || allInScope}
                  onClick={() => applyScope(true)}
                >
                  Mark in scope
                </Button>
                <Button
                  size="small"
                  variant="outlined"
                  disabled={selectedIds.length === 0 || allOutOfScope}
                  onClick={() => applyScope(false)}
                >
                  Mark out
                </Button>
              </Toolbar>
            ) : null}
            <DataList>
              {hosts.map((host) => {
                const scanStatus = host.scan_status || 'idle';
                const running = scanStatus === 'running';
                const finished = scanStatus === 'completed' || scanStatus === 'failed';
                const notebookTo = `/pentest/record/${host.id}?wave=${wave.id}`;
                const scanTo = `/pentest/record/${host.id}/scan-live?wave=${wave.id}`;
                return (
                <DataRow
                  key={host.id}
                  id={host.id}
                  selected={selectedIds.includes(host.id)}
                  leading={
                    canModify && isOpen ? (
                      <Checkbox
                        size="small"
                        checked={selectedIds.includes(host.id)}
                        onChange={() => toggle(host.id)}
                        onClick={(event) => event.stopPropagation()}
                      />
                    ) : null
                  }
                  onToggle={() => navigate(notebookTo)}
                  title={<Mono style={{ fontWeight: 600 }}>{host.name}</Mono>}
                  meta={
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                      <EnvTag slug={host.environment_slug} label={host.environment_name || 'Unassigned'} />
                      <Tag>{host.in_scope === false ? 'out of scope' : 'in scope'}</Tag>
                      <Tag>{host.pentest_status || 'Not Started'}</Tag>
                      <Tag>{host.tested_by ? host.tested_by : 'unassigned'}</Tag>
                      <Tag>{`${host.open_occurrence_count || 0} open · ${host.finding_count || 0} findings`}</Tag>
                      {scanStatus !== 'idle' ? <Tag>{scanStatus}</Tag> : null}
                    </div>
                  }
                  trailing={
                    <div style={{ display: 'flex', gap: 8 }} onClick={(event) => event.stopPropagation()}>
                      {canLaunchScan && isOpen && isStarted && !finished ? (
                        <Button
                          size="small"
                          startIcon={<SmartToy sx={{ fontSize: 16 }} />}
                          onClick={() => onLaunchScan(host)}
                          disabled={scanBusyId === host.id || running}
                        >
                          {running ? 'Scanning…' : 'Launch scan'}
                        </Button>
                      ) : null}
                      {canLaunchScan && isOpen && isStarted && finished ? (
                        <Button
                          size="small"
                          startIcon={<RestartAlt sx={{ fontSize: 16 }} />}
                          onClick={() => onRestartScan(host)}
                          disabled={scanBusyId === host.id || running}
                        >
                          Restart scan
                        </Button>
                      ) : null}
                      {running || finished ? (
                        <Button
                          size="small"
                          component={RouterLink}
                          to={scanTo}
                          startIcon={<Monitor sx={{ fontSize: 16 }} />}
                        >
                          {running ? 'Live' : 'Log'}
                        </Button>
                      ) : null}
                      {canModify && isOpen && isStarted && isWaveTester && onClaimHost && (!host.tested_by || host.tested_by === 'Unassigned') ? (
                        <Button size="small" variant="contained" onClick={() => onClaimHost(host)}>
                          Assign to me
                        </Button>
                      ) : null}
                      {canModify &&
                      isOpen &&
                      isStarted &&
                      isWaveTester &&
                      onClaimHost &&
                      host.tested_by &&
                      host.tested_by !== 'Unassigned' &&
                      host.tested_by !== username ? (
                        <Tag>Assigned to {host.tested_by}</Tag>
                      ) : null}
                      {host.tested_by === username ? <Tag>Yours</Tag> : null}
                      <Button size="small" component={RouterLink} to={notebookTo}>
                        Notebook
                      </Button>
                    </div>
                  }
                />
                );
              })}
            </DataList>
          </div>
        )
      ) : null}

      {section === 'findings' ? (
        findings.length === 0 ? (
          <EmptyState
            title="Nothing found in this wave yet"
            hint="File a finding against a host in this wave after you start it. Earlier waves keep their own findings."
            actions={
              canCreateFinding && isOpen && isStarted ? (
                <Button size="small" variant="contained" onClick={onCreateFinding}>
                  New finding
                </Button>
              ) : null
            }
          />
        ) : (
          <DataList>
            {findings.map((finding) => (
              <FindingCard
                key={finding.id}
                appId={appId}
                finding={finding}
                canModify={canModify}
                busy={busyFinding === finding.id}
                onOccurrenceStatusChange={onOccurrenceStatusChange}
                onOpenTicket={onOpenTicket}
                onOpenMerge={onOpenMerge}
                onPromote={onPromote}
                onAttachHosts={onAttachHosts}
              />
            ))}
          </DataList>
        )
      ) : null}

      <Panel
        open={deleting}
        onClose={() => setDeleting(false)}
        maxWidth="xs"
        title={`Delete “${wave.name}”?`}
        actions={
          <>
            <Button onClick={() => setDeleting(false)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={async () => {
                await onDeleteWave(wave.id);
                setDeleting(false);
              }}
            >
              Delete wave
            </Button>
          </>
        }
      >
        <Text variant="body" tone="secondary">
          The wave record is removed. Findings stay on the application; their wave stamp is cleared.
        </Text>
      </Panel>
    </Page>
  );
};

export default WaveDetailTab;
