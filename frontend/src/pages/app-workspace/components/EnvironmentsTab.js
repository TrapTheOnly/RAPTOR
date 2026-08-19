import React, { useState } from 'react';
import { Add, DeleteOutline } from '@mui/icons-material';
import {
  Button,
  DataList,
  DataRow,
  EmptyState,
  EnvTag,
  Field,
  Mono,
  Panel,
  SwitchRow,
  Tag,
  Text
} from '../../../design/primitives';
import { useNavigate } from 'react-router-dom';

const EnvironmentRow = ({ env, appId, canManage, onDelete }) => {
  const navigate = useNavigate();
  const hostCount = Number(env.host_count || 0);
  const inScope = Number(env.in_scope_count || 0);
  const isUnassigned = env.slug === 'unassigned';

  return (
    <DataRow
      id={env.id}
      onToggle={() => navigate(`/apps/${appId}/envs/${env.id}`)}
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Text variant="bodyStrong">{env.display_name}</Text>
          <Mono tone="secondary">{env.slug}</Mono>
        </div>
      }
      meta={
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
          <EnvTag slug={env.slug} label={env.slug} />
          <Tag>
            {inScope}/{hostCount} in scope
          </Tag>
          {env.is_production ? <Tag emphasized>production</Tag> : null}
          {env.allow_destructive ? <Tag>destructive</Tag> : null}
          {env.include_in_exec_report ? <Tag>export</Tag> : null}
          <Text variant="meta" tone="secondary">
            Max {Number(env.max_concurrent_scans || 1)} concurrent scans
          </Text>
        </div>
      }
      trailing={
        canManage && !isUnassigned ? (
          <Button
            size="small"
            aria-label={`Delete ${env.display_name}`}
            onClick={(event) => {
              event.stopPropagation();
              onDelete(env);
            }}
            onMouseDown={(event) => event.stopPropagation()}
          >
            <DeleteOutline sx={{ fontSize: 16 }} />
          </Button>
        ) : null
      }
    />
  );
};

const EnvironmentsTab = ({ appId, environments, canManage, onCreate, onDelete }) => {
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState({ slug: '', display_name: '', is_production: false });
  const [error, setError] = useState('');

  const submit = async () => {
    const slug = form.slug.trim().toLowerCase();
    if (!/^[a-z0-9-]+$/.test(slug)) {
      setError('Slug can use lowercase letters, numbers, and hyphens only.');
      return;
    }
    if (environments.some((env) => env.slug === slug)) {
      setError('That slug already exists on this application.');
      return;
    }
    if (!form.display_name.trim()) {
      setError('Display name is required.');
      return;
    }
    await onCreate({ ...form, slug, display_name: form.display_name.trim() });
    setCreateOpen(false);
    setForm({ slug: '', display_name: '', is_production: false });
    setError('');
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 16 }}>
        <div>
          <Text as="div" variant="h2">
            Environments
          </Text>
          <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 0', maxWidth: 560 }}>
            Environments are children of this application. One host belongs to exactly one environment.
          </Text>
        </div>
        {canManage ? (
          <Button size="small" variant="contained" startIcon={<Add />} onClick={() => setCreateOpen(true)}>
            New environment
          </Button>
        ) : null}
      </div>

      {environments.length === 0 ? (
        <EmptyState title="No environments yet" hint="Seeded environments appear once the app has hosts." />
      ) : (
        <DataList>
          {environments.map((env) => (
            <EnvironmentRow
              key={env.id}
              env={env}
              appId={appId}
              canManage={canManage}
              onDelete={setDeleteTarget}
            />
          ))}
        </DataList>
      )}

      <Panel
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        maxWidth="xs"
        title="New environment"
        actions={
          <>
            <Button onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button variant="contained" onClick={submit}>
              Create
            </Button>
          </>
        }
      >
        <Field
          label="Slug"
          placeholder="dr"
          value={form.slug}
          hint="Short identifier used in host filing and exports."
          onChange={(event) => setForm((prev) => ({ ...prev, slug: event.target.value }))}
        />
        <Field
          label="Display name"
          placeholder="Disaster Recovery"
          value={form.display_name}
          onChange={(event) => setForm((prev) => ({ ...prev, display_name: event.target.value }))}
        />
        <SwitchRow
          label="Production environment"
          hint="Emphasised in the console and defaulted onto owner packs."
          checked={form.is_production}
          onChange={(value) => setForm((prev) => ({ ...prev, is_production: value }))}
        />
        {error ? (
          <Text variant="meta" tone="critical">
            {error}
          </Text>
        ) : null}
      </Panel>

      <Panel
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        maxWidth="xs"
        title="Delete environment"
        actions={
          <>
            <Button onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button
              variant="contained"
              color="error"
              onClick={() => {
                const env = deleteTarget;
                setDeleteTarget(null);
                if (env) onDelete(env);
              }}
            >
              Delete
            </Button>
          </>
        }
      >
        <Text as="p" variant="body" style={{ margin: 0 }}>
          Confirm delete
          {deleteTarget?.display_name ? ` of ${deleteTarget.display_name}` : ''}.
        </Text>
      </Panel>
    </div>
  );
};

export default EnvironmentsTab;
