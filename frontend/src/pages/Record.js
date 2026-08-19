import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link as RouterLink } from 'react-router-dom';
import { ArrowBack } from '@mui/icons-material';
import {
  Button,
  EmptyState,
  EnvTag,
  Field,
  Mono,
  Page,
  PageHeader,
  Progress,
  StatusGlyph,
  Surface,
  Tag,
  Text,
  Toast
} from '../design/primitives';
import { hasPermission as hasRolePermission } from '../utils/permissions';
import { RADIUS, SPACE } from '../design/tokens';
import {
  getRecordByDomain,
  getRecordById,
  getRecordHistory,
  getSessionStatus,
  updateRecordById
} from './records-table/services';
import { historyFieldDiffs, formatDateTimeFull } from './records-table/utils';
import { usePalette } from '../design/usePalette';

const DiffValue = ({ value, mono, tone = 'primary', strong = false }) => {
  const text = value || '—';
  if (mono) {
    return (
      <Mono tone={tone} style={{ fontWeight: strong ? 600 : 400 }}>
        {text}
      </Mono>
    );
  }
  return (
    <Text variant="body" tone={tone} style={{ fontWeight: strong ? 600 : 400 }}>
      {text}
    </Text>
  );
};

const HistoryEvent = ({ item, palette }) => {
  const diffs = historyFieldDiffs(item);
  const action = String(item.action || 'updated').replace(/_/g, ' ');
  return (
    <div style={{ padding: 16, borderTop: `1px solid ${palette.line}` }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 12,
          flexWrap: 'wrap',
          marginBottom: diffs.length ? 12 : 0
        }}
      >
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
          <Tag>{action}</Tag>
          <Text variant="bodyStrong">{item.username || 'System'}</Text>
        </span>
        <Mono tone="secondary">{formatDateTimeFull(item.timestamp)}</Mono>
      </div>
      {diffs.length === 0 ? (
        <Text variant="meta" tone="secondary">
          No field-level diff stored for this event.
        </Text>
      ) : (
        <div
          style={{
            display: 'grid',
            gap: 16,
            gridTemplateColumns: `repeat(${Math.min(diffs.length, 3)}, minmax(160px, 1fr))`
          }}
        >
          {diffs.map((field) => (
            <div key={field.key}>
              <Text as="div" variant="micro" tone="tertiary">
                {field.label}
              </Text>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 4, minWidth: 0 }}>
                <DiffValue value={field.old} mono={field.mono} tone="tertiary" />
                <Text variant="micro" tone="tertiary">
                  →
                </Text>
                <DiffValue value={field.next} mono={field.mono} strong />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const Fact = ({ label, children }) => (
  <div>
    <Text as="div" variant="micro" tone="tertiary">
      {label}
    </Text>
    <div style={{ marginTop: 4 }}>{children}</div>
  </div>
);

const portList = (value) =>
  String(value || '')
    .split(',')
    .map((port) => port.trim())
    .filter(Boolean);

const Record = ({ userPermissions, userRole }) => {
  const [record, setRecord] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingDescription, setEditingDescription] = useState(false);
  const [editedDescription, setEditedDescription] = useState('');
  const [toast, setToast] = useState(null);
  const { domain, recordId } = useParams();
  const navigate = useNavigate();
  const palette = usePalette();
  const canModifyRecords = hasRolePermission(userRole, userPermissions, 'modify_records');
  const canViewWorkspace = hasRolePermission(userRole, userPermissions, 'view_security_dashboard');

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError('');
      try {
        const session = await getSessionStatus();
        if (session.status !== 200) {
          navigate('/login');
          return;
        }
        const recordResponse = recordId ? await getRecordById(recordId) : await getRecordByDomain(domain);
        setRecord(recordResponse.data);
        setEditedDescription(recordResponse.data.description || '');
        const historyResponse = await getRecordHistory(recordResponse.data.id);
        setHistory(historyResponse.data || []);
        if (!recordId && domain && recordResponse.data?.id) {
          navigate(`/records/record/${recordResponse.data.id}`, { replace: true });
        }
      } catch (err) {
        setError('Failed to load this asset.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [domain, navigate, recordId]);

  const handleSaveDescription = async () => {
    if (!canModifyRecords || !record) return;
    try {
      await updateRecordById(record.id, { ...record, description: editedDescription });
      const refreshed = await getRecordById(record.id);
      setRecord(refreshed.data);
      setEditingDescription(false);
    } catch (saveError) {
      console.error('Error updating description:', saveError);
      setToast({ message: 'Failed to update description.', severity: 'error' });
    }
  };

  const ports = portList(record?.open_ports);
  const hasConflict = Boolean(record?.sync_conflict);

  return (
    <Page>
      <PageHeader
        crumbs={[{ label: 'Assets', to: '/records' }, { label: record?.name || 'Asset' }]}
        leading={
          <Button size="small" startIcon={<ArrowBack sx={{ fontSize: 16 }} />} onClick={() => navigate('/records')}>
            Back to Assets
          </Button>
        }
        title={record?.name || 'Asset'}
        subtitle={record ? `${record.ip_address || 'No IP'} · ${record.source || 'Unknown source'}` : 'Host in the asset inventory'}
        meta={
          record ? (
            <span style={{ display: 'inline-flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <StatusGlyph status={record.status} />
              {record.origin === 'manual' ? <Tag>Manual</Tag> : <Tag>Automated</Tag>}
              {hasConflict ? <Tag emphasized>Conflict</Tag> : null}
            </span>
          ) : null
        }
      />

      {loading ? <Progress deferred /> : null}

      {error ? (
        <EmptyState
          title="Could not load asset"
          hint={error}
          actions={
            <Button variant="outlined" onClick={() => navigate('/records')}>
              Back to Assets
            </Button>
          }
        />
      ) : null}

      {!loading && !error && !record ? (
        <EmptyState
          title="Asset not found"
          hint="This host is not in inventory, or you do not have access."
          actions={
            <Button variant="outlined" onClick={() => navigate('/records')}>
              Back to Assets
            </Button>
          }
        />
      ) : null}

      {record && !error ? (
        <div style={{ display: 'grid', gap: 16 }}>
          {hasConflict ? (
            <Surface style={{ padding: 16, borderColor: palette.severity.critical }}>
              <Text as="p" variant="meta" tone="critical" style={{ margin: 0 }}>
                This manual domain matches imported DNS data
                {record.sync_conflict_reason ? ` (${record.sync_conflict_reason})` : ''} and needs admin resolution
                from the asset inventory.
              </Text>
            </Surface>
          ) : null}

          <div
            style={{
              display: 'grid',
              gap: 16,
              gridTemplateColumns: 'minmax(0, 1.6fr) minmax(260px, 0.8fr)'
            }}
          >
            <Surface style={{ padding: 16, borderRadius: RADIUS.panel }}>
              <Text as="div" variant="h2" style={{ marginBottom: 16 }}>
                Asset
              </Text>
              <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
                <Fact label="Hostname">
                  <Mono style={{ fontWeight: 600 }}>{record.name}</Mono>
                </Fact>
                <Fact label="IP address">
                  <Mono>{record.ip_address || '—'}</Mono>
                </Fact>
                <Fact label="Application">
                  {record.application_id && canViewWorkspace ? (
                    <Button
                      size="small"
                      component={RouterLink}
                      to={`/apps/${record.application_id}`}
                      style={{ paddingLeft: 0 }}
                    >
                      {record.application_name}
                    </Button>
                  ) : (
                    <Text variant="body">{record.application_name || 'Unassigned'}</Text>
                  )}
                </Fact>
                <Fact label="Environment">
                  <EnvTag slug={record.environment_slug} label={record.environment_name || 'Unassigned'} />
                </Fact>
                <Fact label="Owner">
                  <Text variant="body">{record.application_owner || 'Not assigned'}</Text>
                </Fact>
                <Fact label="Maintainer">
                  <Text variant="body">{record.maintainer || 'Not assigned'}</Text>
                </Fact>
                <Fact label="Open ports">
                  {ports.length ? (
                    <span style={{ display: 'inline-flex', gap: 6, flexWrap: 'wrap' }}>
                      {ports.map((port) => (
                        <Tag key={port}>
                          <Mono style={{ fontSize: 11 }}>{port}</Mono>
                        </Tag>
                      ))}
                    </span>
                  ) : (
                    <Text variant="body" tone="secondary">
                      None recorded
                    </Text>
                  )}
                </Fact>
                <Fact label="Scope">
                  <Tag emphasized={Boolean(record.in_scope)}>{record.in_scope ? 'In scope' : 'Out of scope'}</Tag>
                </Fact>
              </div>
            </Surface>

            <Surface style={{ padding: 16, borderRadius: RADIUS.panel }}>
              <Text as="div" variant="h2" style={{ marginBottom: 16 }}>
                Registry
              </Text>
              <div style={{ display: 'grid', gap: 16 }}>
                <Fact label="Record ID">
                  <Mono>{record.id}</Mono>
                </Fact>
                <Fact label="Origin">
                  <Text variant="body">{record.origin === 'manual' ? 'Manual' : 'Automated import'}</Text>
                </Fact>
                <Fact label="Source">
                  <Text variant="body">{record.source || '—'}</Text>
                </Fact>
                <Fact label="Created">
                  <Mono tone="secondary">{formatDateTimeFull(record.creation_date)}</Mono>
                </Fact>
                <Fact label="Last modified">
                  <Mono tone="secondary">{formatDateTimeFull(record.last_modification_date)}</Mono>
                </Fact>
                {record.env_suggestion ? (
                  <Fact label="Environment suggestion">
                    <Text variant="body">{record.env_suggestion}</Text>
                  </Fact>
                ) : null}
              </div>
            </Surface>
          </div>

          <Surface style={{ padding: 16, borderRadius: RADIUS.panel }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-end', marginBottom: 12 }}>
              <Text as="div" variant="h2">
                Description
              </Text>
              {canModifyRecords && !editingDescription ? (
                <Button size="small" onClick={() => setEditingDescription(true)}>
                  Edit
                </Button>
              ) : null}
            </div>
            {editingDescription ? (
              <div>
                <Field
                  label="Description"
                  value={editedDescription}
                  onChange={(event) => setEditedDescription(event.target.value)}
                  multiline
                  minRows={4}
                  placeholder="What this host is for, who owns it, and how it should be handled."
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 12, justifyContent: 'flex-end' }}>
                  <Button
                    size="small"
                    onClick={() => {
                      setEditingDescription(false);
                      setEditedDescription(record.description || '');
                    }}
                  >
                    Cancel
                  </Button>
                  <Button size="small" variant="contained" onClick={handleSaveDescription}>
                    Save
                  </Button>
                </div>
              </div>
            ) : (
              <Text
                as="p"
                variant="body"
                tone={record.description ? 'primary' : 'secondary'}
                style={{ margin: 0, whiteSpace: 'pre-wrap' }}
              >
                {record.description || 'No description'}
              </Text>
            )}
          </Surface>

          <Surface style={{ borderRadius: RADIUS.panel, overflow: 'hidden' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 16 }}>
              <Text as="div" variant="h2">
                Change history
              </Text>
              <Tag>{`${history.length} event${history.length === 1 ? '' : 's'}`}</Tag>
            </div>
            {history.length === 0 ? (
              <div style={{ padding: `0 16px ${SPACE.x16}px` }}>
                <Text variant="meta" tone="secondary">
                  No recorded changes for this host.
                </Text>
              </div>
            ) : (
              history.map((item) => <HistoryEvent key={item.id} item={item} palette={palette} />)
            )}
          </Surface>
        </div>
      ) : null}

      <Toast
        open={Boolean(toast)}
        message={toast?.message}
        severity={toast?.severity}
        onClose={() => setToast(null)}
      />
    </Page>
  );
};

export default Record;
