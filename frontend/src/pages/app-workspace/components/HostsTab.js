import React, { useEffect, useMemo, useState } from 'react';
import { Checkbox, InputAdornment, Pagination } from '@mui/material';
import { Link as RouterLink } from 'react-router-dom';
import { Add, Dns, MoveDown, Search, Share } from '@mui/icons-material';
import {
  Button,
  Combo,
  DataList,
  DataRow,
  EmptyState,
  EnvTag,
  Field,
  Mono,
  Panel,
  Tag,
  Text,
  Toolbar
} from '../../../design/primitives';
import { searchHosts } from '../services';

const HostRow = ({
  host,
  selected,
  onToggle,
  canManage,
  onShare,
  selectable
}) => {
  const scanStatus = host.scan_status || 'idle';
  return (
    <DataRow
      id={host.id}
      selected={selected}
      leading={
        selectable ? (
          <Checkbox
            size="small"
            checked={selected}
            onChange={() => onToggle(host.id)}
            onClick={(event) => event.stopPropagation()}
          />
        ) : null
      }
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <Mono style={{ fontWeight: 600 }}>{host.name}</Mono>
          {host.ip_address ? (
            <Mono tone="secondary" style={{ fontSize: 12 }}>
              {host.ip_address}
            </Mono>
          ) : null}
        </div>
      }
      meta={
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', marginTop: 4 }}>
          <EnvTag slug={host.environment_slug} label={host.environment_name || 'Unassigned'} />
          <Tag>{`${host.open_occurrence_count || 0} open · ${host.finding_count || 0} findings`}</Tag>
          {scanStatus !== 'idle' ? <Tag>{scanStatus}</Tag> : null}
          {host.env_suggestion && host.environment_slug !== host.env_suggestion ? (
            <Tag>suggests {host.env_suggestion}</Tag>
          ) : null}
        </div>
      }
      trailing={
        <div style={{ display: 'flex', gap: 4 }} onClick={(event) => event.stopPropagation()}>
          {canManage ? (
            <Button size="small" startIcon={<Share sx={{ fontSize: 16 }} />} onClick={() => onShare(host)}>
              Share
            </Button>
          ) : null}
        </div>
      }
    />
  );
};

const HostsTab = ({
  hosts,
  total,
  page,
  pageSize,
  onPageChange,
  loading,
  search,
  onSearchChange,
  envFilter,
  onEnvFilterChange,
  environments,
  canManage,
  onBulkAssign,
  onShare,
  onAddHosts
}) => {
  const [selectedIds, setSelectedIds] = useState([]);
  const [targetEnvId, setTargetEnvId] = useState('');
  const [addOpen, setAddOpen] = useState(false);
  const [addQuery, setAddQuery] = useState('');
  const [addResults, setAddResults] = useState([]);
  const [addSelected, setAddSelected] = useState([]);
  const [addEnvId, setAddEnvId] = useState('');
  const [addBusy, setAddBusy] = useState(false);

  const assignableEnvs = useMemo(
    () => environments.filter((env) => env.slug !== 'unassigned'),
    [environments]
  );

  const toggle = (id) =>
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));

  const allSelected = hosts.length > 0 && selectedIds.length > 0 && hosts.every((host) => selectedIds.includes(host.id));
  const pageCount = Math.max(1, Math.ceil((total || 0) / pageSize));

  const runBulk = async (payload) => {
    await onBulkAssign({ record_ids: selectedIds, ...payload });
    setSelectedIds([]);
  };

  useEffect(() => {
    if (!addOpen) return undefined;
    const term = addQuery.trim();
    if (term.length < 2) {
      setAddResults([]);
      return undefined;
    }
    let cancelled = false;
    const handle = setTimeout(async () => {
      try {
        const response = await searchHosts({ q: term, limit: 20 });
        if (!cancelled) setAddResults(response.data.hosts || []);
      } catch (error) {
        if (!cancelled) setAddResults([]);
      }
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [addQuery, addOpen]);

  const toggleAdd = (id) =>
    setAddSelected((prev) => (prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]));

  const submitAdd = async () => {
    if (!addSelected.length || !addEnvId || !onAddHosts) return;
    setAddBusy(true);
    try {
      await onAddHosts({ record_ids: addSelected, environment_id: Number(addEnvId) });
      setAddOpen(false);
      setAddQuery('');
      setAddResults([]);
      setAddSelected([]);
      setAddEnvId('');
    } finally {
      setAddBusy(false);
    }
  };

  return (
    <div>
      <Toolbar>
        <Field
          label="Search"
          placeholder="Search hosts by name"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          style={{ flex: '1 1 240px', minWidth: 220 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <Search sx={{ fontSize: 16 }} />
              </InputAdornment>
            )
          }}
        />
        {onEnvFilterChange ? (
          <Combo
            label="Environment"
            options={[
              { value: '', label: 'All environments' },
              ...environments.map((env) => ({ value: env.id, label: env.display_name }))
            ]}
            value={envFilter}
            onChange={onEnvFilterChange}
            fullWidth={false}
            style={{ width: 180 }}
          />
        ) : null}
        <Text variant="meta" tone="secondary" style={{ paddingBottom: 8 }}>
          {total} host{total === 1 ? '' : 's'}
        </Text>
        {canManage && onAddHosts ? (
          <Button size="small" variant="contained" startIcon={<Add />} onClick={() => setAddOpen(true)}>
            Add hosts
          </Button>
        ) : null}
      </Toolbar>

      {canManage ? (
        <Toolbar>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 11, lineHeight: '12px', visibility: 'hidden' }}>Select</span>
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
          </div>
          <div style={{ flexGrow: 1, minWidth: 8 }} />
          <Combo
            label="Move to environment"
            options={assignableEnvs.map((env) => ({
              value: env.id,
              label: `${env.display_name} (${env.slug})`
            }))}
            value={targetEnvId}
            onChange={setTargetEnvId}
            disabled={selectedIds.length === 0}
            fullWidth={false}
            placeholder="Choose environment"
            disableClearable={false}
            style={{ width: 220 }}
          />
          <Button
            size="small"
            variant="contained"
            startIcon={<MoveDown />}
            disabled={selectedIds.length === 0 || !targetEnvId}
            onClick={() => runBulk({ environment_id: Number(targetEnvId) })}
          >
            Move
          </Button>
        </Toolbar>
      ) : null}

      {hosts.length === 0 ? (
        <EmptyState
          icon={Dns}
          title={search ? 'No hosts match that search' : 'No hosts in this view'}
          hint={
            search
              ? 'Try a shorter fragment of the hostname.'
              : 'Add hosts from Records, or file them into an environment here.'
          }
          actions={
            canManage && onAddHosts ? (
              <Button variant="contained" startIcon={<Add />} onClick={() => setAddOpen(true)}>
                Add hosts
              </Button>
            ) : (
              <Button component={RouterLink} to="/records" variant="outlined">
                Open Records
              </Button>
            )
          }
        />
      ) : (
        <DataList>
          {hosts.map((host) => (
            <HostRow
              key={host.id}
              host={host}
              selected={selectedIds.includes(host.id)}
              onToggle={toggle}
              canManage={canManage}
              onShare={onShare}
              selectable={canManage}
            />
          ))}
        </DataList>
      )}

      {pageCount > 1 ? (
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 16 }}>
          <Pagination count={pageCount} page={page} onChange={(_event, value) => onPageChange(value)} disabled={loading} />
        </div>
      ) : null}

      <Panel
        open={addOpen}
        onClose={() => setAddOpen(false)}
        title="Add hosts"
        actions={
          <>
            <Button onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button
              variant="contained"
              disabled={addBusy || addSelected.length === 0 || !addEnvId}
              onClick={submitAdd}
            >
              Add {addSelected.length || ''} to environment
            </Button>
          </>
        }
      >
        <Text as="p" variant="meta" tone="secondary" style={{ margin: '0 0 12px' }}>
          Search Records and file hosts into an environment. In-scope is decided later on each wave.
        </Text>
        <Field
          autoFocus
          label="Search"
          placeholder="Hostname fragment"
          value={addQuery}
          onChange={(event) => setAddQuery(event.target.value)}
        />
        <Combo
          label="Environment"
          options={assignableEnvs.map((env) => ({
            value: env.id,
            label: `${env.display_name} (${env.slug})`
          }))}
          value={addEnvId}
          onChange={setAddEnvId}
          placeholder="File into…"
        />
        {addResults.length === 0 ? (
          <Text variant="meta" tone="secondary">
            {addQuery.trim().length < 2 ? 'Type at least two characters.' : 'No matching records.'}
          </Text>
        ) : (
          <DataList>
            {addResults.map((host) => (
              <DataRow
                key={host.id}
                id={host.id}
                selected={addSelected.includes(host.id)}
                leading={
                  <Checkbox
                    size="small"
                    checked={addSelected.includes(host.id)}
                    onChange={() => toggleAdd(host.id)}
                    onClick={(event) => event.stopPropagation()}
                  />
                }
                onToggle={() => toggleAdd(host.id)}
                title={<Mono style={{ fontWeight: 600 }}>{host.name}</Mono>}
                meta={
                  <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
                    {host.ip_address ? <Mono tone="secondary">{host.ip_address}</Mono> : null}
                    <EnvTag
                      slug={host.environment_slug || 'unassigned'}
                      label={host.environment_name || host.application_name || 'Unassigned'}
                    />
                  </div>
                }
              />
            ))}
          </DataList>
        )}
      </Panel>
    </div>
  );
};

export default HostsTab;
