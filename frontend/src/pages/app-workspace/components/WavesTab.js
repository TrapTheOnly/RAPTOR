import React, { useState } from 'react';
import { Alert } from '@mui/material';
import { Add, DeleteOutline, FileDownload, Flag, StopCircle } from '@mui/icons-material';
import {
  Button,
  Combo,
  DataList,
  DataRow,
  EmptyState,
  EnvTag,
  Field,
  Panel,
  Tag,
  Text
} from '../../../design/primitives';

const formatDate = (value) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
};

const WaveRow = ({ wave, environments, canExport, canModify, canDelete, onEnd, onExport, onDelete, onOpen }) => {
  const isOpen = wave.status === 'open';
  const isStarted = Boolean(wave.started_at || wave.started);
  const statusLabel = !isOpen ? 'ended' : isStarted ? 'in progress' : 'not started';
  const envIds = wave.env_ids?.length ? wave.env_ids : wave.environment_id ? [wave.environment_id] : [];
  const envs = envIds
    .map((id) => environments.find((item) => String(item.id) === String(id)))
    .filter(Boolean);

  return (
    <DataRow
      id={wave.id}
      onToggle={() => onOpen(wave)}
      title={<Text variant="bodyStrong">{wave.name}</Text>}
      meta={
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 4 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <Tag>{statusLabel}</Tag>
            <Text variant="meta" tone="secondary">
              Opened {formatDate(wave.opened_at)} by {wave.opened_by || 'unknown'}
              {wave.closed_at ? ` · ended ${formatDate(wave.closed_at)}` : ''}
            </Text>
            <Text variant="meta" tone="secondary">
              {wave.host_count || 0} live hosts
            </Text>
            {envs.length
              ? envs.map((env) => <EnvTag key={env.id} slug={env.slug} label={env.slug} />)
              : wave.environment_slug
                ? <EnvTag slug={wave.environment_slug} label={wave.environment_slug} />
                : <Tag>no environment</Tag>}
            {(wave.members || []).length > 0 ? (
              <Tag>{`${wave.members.length} tester${wave.members.length === 1 ? '' : 's'}`}</Tag>
            ) : null}
          </div>
          {wave.notes ? (
            <Text variant="meta" tone="secondary" style={{ whiteSpace: 'pre-line' }}>
              {wave.notes}
            </Text>
          ) : null}
        </div>
      }
      trailing={
        <div style={{ display: 'flex', gap: 8 }} onClick={(event) => event.stopPropagation()}>
          {canExport ? (
            <Button size="small" variant="contained" startIcon={<FileDownload sx={{ fontSize: 16 }} />} onClick={() => onExport(wave)}>
              Export
            </Button>
          ) : null}
          {canModify && isOpen ? (
            <Button size="small" startIcon={<StopCircle sx={{ fontSize: 16 }} />} onClick={() => onEnd(wave)}>
              End wave
            </Button>
          ) : null}
          {canDelete ? (
            <Button size="small" startIcon={<DeleteOutline />} onClick={() => onDelete(wave)}>
              Delete
            </Button>
          ) : null}
        </div>
      }
    />
  );
};

const WavesTab = ({
  waves,
  environments,
  canModify,
  canExport,
  canDelete,
  onCreate,
  onEnd,
  onExport,
  onDelete,
  onOpen,
  pentestUsers = [],
  environmentName,
  defaultEnvIds = []
}) => {
  const [createOpen, setCreateOpen] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [ending, setEnding] = useState(null);
  const [form, setForm] = useState({ name: '', env_ids: defaultEnvIds, notes: '', members: [] });

  const openWaves = waves.filter((wave) => wave.status === 'open');
  const closedWaves = waves.filter((wave) => wave.status !== 'open');
  const envOptions = environments
    .filter((env) => env.slug !== 'unassigned')
    .map((env) => ({ value: env.id, label: `${env.display_name} (${env.slug})` }));

  const submit = async () => {
    await onCreate(form);
    setForm({ name: '', env_ids: defaultEnvIds, notes: '', members: [] });
    setCreateOpen(false);
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 16 }}>
        <div>
          <Text as="div" variant="h2">
            Engagement waves
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 0', maxWidth: 560 }}>
            {environmentName
              ? `Waves that include ${environmentName}. Start a wave to mark hosts In Progress, file findings, and launch scans.`
              : 'A wave is the engagement between the customer and the testers. Start it to mark hosts In Progress, file findings, and launch scans. Export a report at any time. Ending freezes the engagement.'}
          </Text>
        </div>
        {canModify ? (
          <Button
            size="small"
            variant="contained"
            startIcon={<Add />}
            onClick={() => {
              setForm({ name: '', env_ids: defaultEnvIds, notes: '', members: [] });
              setCreateOpen(true);
            }}
          >
            Open wave
          </Button>
        ) : null}
      </div>

      {waves.length === 0 ? (
        <EmptyState
          icon={Flag}
          title={environmentName ? `No waves in ${environmentName}` : 'No waves yet'}
          hint={
            environmentName
              ? 'Open a wave that includes this environment. Ended waves that used it stay listed here.'
              : 'Open a wave against the environments you will test. Findings are filed on the wave. Export a report at any time. Ending freezes the engagement.'
          }
        />
      ) : (
        <DataList>
          {[...openWaves, ...closedWaves].map((wave) => (
            <WaveRow
              key={wave.id}
              wave={wave}
              environments={environments}
              canExport={canExport}
              canModify={canModify}
              canDelete={canDelete}
              onEnd={setEnding}
              onExport={onExport}
              onDelete={setDeleting}
              onOpen={onOpen}
            />
          ))}
        </DataList>
      )}

      <Panel
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Open engagement wave"
        actions={
          <>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              disabled={!form.name.trim() || !(form.env_ids || []).length}
              onClick={submit}
            >
              Open wave
            </Button>
          </>
        }
      >
        <Alert severity="info">
          Hosts currently in the selected environments appear on the wave immediately. You can add environments later.
        </Alert>
        <Field
          autoFocus
          label="Wave name"
          placeholder="2026 H1 production assessment"
          value={form.name}
          onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
        />
        <Combo
          label="Environments"
          placeholder="Pick one or more environments"
          multiple
          options={envOptions}
          value={form.env_ids}
          onChange={(value) => setForm((prev) => ({ ...prev, env_ids: value || [] }))}
        />
        <Combo
          label="Testers"
          placeholder="Add pentest users on this wave"
          multiple
          freeSolo
          mode="enum"
          options={[...new Set((pentestUsers || []).filter(Boolean))].map((name) => ({
            value: name,
            label: name
          }))}
          value={form.members || []}
          onChange={(value) => setForm((prev) => ({ ...prev, members: value || [] }))}
          hint="Everyone listed collaborates on every live host. You can change this later on the wave."
        />
        <Field
          multiline
          minRows={3}
          label="Notes"
          placeholder="Vendor, contract reference, or scope caveats"
          value={form.notes}
          onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
        />
      </Panel>

      <Panel
        open={Boolean(ending)}
        onClose={() => setEnding(null)}
        maxWidth="xs"
        title={ending ? `End “${ending.name}”?` : 'End wave'}
        actions={
          <>
            <Button onClick={() => setEnding(null)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={async () => {
                await onEnd(ending);
                setEnding(null);
              }}
            >
              End wave
            </Button>
          </>
        }
      >
        <Text variant="body" tone="secondary">
          Members, hosts, scans, and findings become read-only. You can still export a report afterwards. The wave
          cannot be reopened.
        </Text>
      </Panel>

      <Panel
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        maxWidth="xs"
        title={deleting ? `Delete “${deleting.name}”?` : 'Delete wave'}
        actions={
          <>
            <Button onClick={() => setDeleting(null)}>Cancel</Button>
            <Button
              variant="contained"
              onClick={async () => {
                await onDelete(deleting.id);
                setDeleting(null);
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
    </div>
  );
};

export default WavesTab;
