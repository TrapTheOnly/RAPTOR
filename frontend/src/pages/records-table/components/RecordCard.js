import React from 'react';
import { History } from '@mui/icons-material';
import { motion } from 'motion/react';
import {
  Button,
  Combo,
  EnvTag,
  Field,
  Mono,
  StatusGlyph,
  Tag,
  Text
} from '../../../design/primitives';
import { FONTS, RADIUS, ROW, SPACE } from '../../../design/tokens';
import { DURATION, CSS_EASE, disclosureVariants } from '../../../design/motion';
import { usePalette } from '../../../design/usePalette';
import { INVENTORY_CELL, INVENTORY_COL_COUNT_FLAT, INVENTORY_COL_COUNT_GROUPED } from '../constants';
import { firstPorts, formatDateTime } from '../utils';

const Detail = ({ label, children }) => (
  <div>
    <Text as="div" variant="micro" tone="tertiary">
      {label}
    </Text>
    <div style={{ marginTop: 4 }}>{children}</div>
  </div>
);

const RecordCard = ({
  record,
  grouped = false,
  isExpanded,
  isEditing,
  editForm,
  apps,
  environments = [],
  canModifyRecords,
  canDeleteRecords,
  canResolveSyncConflicts,
  canViewRecordDetails,
  onToggleExpanded,
  onUpdateEditForm,
  onStartEditing,
  onSave,
  onCancelEditing,
  onDelete,
  onResolveSyncConflict,
  onOpenHistory
}) => {
  const palette = usePalette();
  const hasSyncConflict = Boolean(record.sync_conflict);
  const selectedApp =
    apps.find((app) => Number(app.id) === Number(editForm.application_id)) || null;
  const selectedEnv =
    environments.find((env) => Number(env.id) === Number(editForm.environment_id)) || null;
  const rail =
    hasSyncConflict || record.status === 'missing' ? palette.severity.critical : 'transparent';
  const colSpan = grouped ? INVENTORY_COL_COUNT_GROUPED : INVENTORY_COL_COUNT_FLAT;
  const ports = firstPorts(record.open_ports);
  const hoverRow = (event, on) => {
    event.currentTarget.style.background = on ? palette.hover : 'transparent';
  };

  const cell = {
    ...INVENTORY_CELL,
    borderBottom: isExpanded ? 0 : `1px solid ${palette.line}`
  };

  return (
    <>
      <tr
        onClick={() => {
          if (isEditing) return;
          onToggleExpanded(record.id);
        }}
        onKeyDown={(event) => {
          if (isEditing) return;
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            onToggleExpanded(record.id);
          }
        }}
        onMouseEnter={(event) => hoverRow(event, true)}
        onMouseLeave={(event) => hoverRow(event, false)}
        tabIndex={0}
        style={{
          cursor: 'pointer',
          height: ROW.base,
          background: 'transparent',
          transition: `background-color ${DURATION.instant}ms ${CSS_EASE.enter}`
        }}
      >
        <td style={{ ...cell, width: 28, paddingRight: 0 }}>
          <span
            aria-hidden
            style={{
              display: 'block',
              width: 2,
              height: 20,
              borderRadius: RADIUS.chip,
              background: rail
            }}
          />
        </td>
        <td style={cell}>
          <Mono title={record.name} style={{ fontWeight: 600 }}>
            {record.name}
          </Mono>
        </td>
        <td style={cell}>
          <Mono title={record.ip_address || ''} tone="secondary" style={{ fontSize: 12 }}>
            {record.ip_address || '—'}
          </Mono>
        </td>
        <td style={cell}>
          <StatusGlyph status={record.status} />
        </td>
        <td style={cell}>
          <Text variant="micro" tone="secondary">
            {record.origin === 'manual' ? 'Manual' : 'Auto'}
          </Text>
        </td>
        <td style={cell}>
          <Mono tone="secondary" style={{ fontSize: 12 }}>
            {record.source || '—'}
          </Mono>
        </td>
        {grouped ? null : (
          <td style={cell}>
            <Text variant="body">{record.application_name || 'Unassigned'}</Text>
          </td>
        )}
        <td style={cell}>
          <EnvTag slug={record.environment_slug} label={record.environment_name || 'Unassigned'} />
        </td>
        <td style={cell}>
          <Text variant="meta" tone="secondary">
            {formatDateTime(record.last_modification_date)}
          </Text>
        </td>
        <td style={{ ...cell, textAlign: 'right' }} onClick={(event) => event.stopPropagation()}>
          <span style={{ display: 'inline-flex', justifyContent: 'flex-end', gap: 6, alignItems: 'center' }}>
            {hasSyncConflict ? <Tag emphasized>Conflict</Tag> : null}
            {canModifyRecords ? (
              <Button
                size="small"
                onClick={() => {
                  if (!isExpanded) onToggleExpanded(record.id);
                  onStartEditing(record);
                }}
              >
                Edit
              </Button>
            ) : null}
          </span>
        </td>
      </tr>
      {isExpanded ? (
        <tr>
          <td colSpan={colSpan} style={{ padding: 0, borderBottom: `1px solid ${palette.line}`, width: '100%', maxWidth: 0 }}>
            <motion.div
              key={`${record.id}-body`}
              variants={disclosureVariants}
              initial="initial"
              animate="animate"
              style={{ overflow: 'hidden' }}
            >
                <div style={{ padding: `${SPACE.x16}px ${SPACE.x16}px ${SPACE.x16}px 40px` }}>
                  {hasSyncConflict ? (
                    <Text as="p" variant="meta" tone="critical" style={{ margin: '0 0 12px' }}>
                      This manual domain matches imported DNS data and needs admin resolution.
                    </Text>
                  ) : null}
                  {isEditing ? (
                    <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(3, minmax(220px, 1fr))' }}>
                      <Combo
                        label="Application"
                        options={apps}
                        value={selectedApp}
                        onChange={(app) =>
                          onUpdateEditForm({
                            ...editForm,
                            application_id: app?.id || '',
                            environment_id: ''
                          })
                        }
                        getOptionLabel={(app) => app?.name || ''}
                        placeholder="Unassigned"
                        disableClearable={false}
                        mode="entity"
                      />
                      <Combo
                        label="Environment"
                        options={environments}
                        value={selectedEnv}
                        onChange={(env) => onUpdateEditForm({ ...editForm, environment_id: env?.id || '' })}
                        getOptionLabel={(env) => env?.display_name || env?.name || ''}
                        placeholder="Unassigned"
                        disableClearable={false}
                        disabled={!editForm.application_id}
                        mode="entity"
                      />
                      <Field
                        label="Application owner"
                        value={editForm.application_owner}
                        onChange={(event) =>
                          onUpdateEditForm({ ...editForm, application_owner: event.target.value })
                        }
                      />
                      <Field
                        label="Maintainer"
                        value={editForm.maintainer}
                        onChange={(event) => onUpdateEditForm({ ...editForm, maintainer: event.target.value })}
                      />
                      <Field
                        label="Open ports"
                        value={editForm.open_ports}
                        onChange={(event) =>
                          onUpdateEditForm({ ...editForm, open_ports: event.target.value })
                        }
                        placeholder="22, 80, 443, 8080"
                        hint="Comma-separated port numbers"
                        InputProps={{ sx: { fontFamily: FONTS.mono } }}
                      />
                      <Field
                        label="Description"
                        value={editForm.description}
                        onChange={(event) =>
                          onUpdateEditForm({ ...editForm, description: event.target.value })
                        }
                        multiline
                        minRows={3}
                        style={{ gridColumn: '1 / -1' }}
                      />
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(3, minmax(180px, 1fr))' }}>
                      <Detail label="Application">
                        <Text variant="body">{record.application_name || 'Unassigned'}</Text>
                      </Detail>
                      <Detail label="Environment">
                        <EnvTag
                          slug={record.environment_slug}
                          label={record.environment_name || 'Unassigned'}
                        />
                      </Detail>
                      <Detail label="Owner">
                        <Text variant="body">{record.application_owner || 'Not assigned'}</Text>
                      </Detail>
                      <Detail label="Maintainer">
                        <Text variant="body">{record.maintainer || 'Not assigned'}</Text>
                      </Detail>
                      <Detail label="Open ports">
                        <Mono title={ports.title}>{ports.label}</Mono>
                      </Detail>
                      <Detail label="Scope">
                        <Text variant="body">{record.in_scope ? 'In scope' : 'Not in scope'}</Text>
                      </Detail>
                      <div style={{ gridColumn: '1 / -1' }}>
                        <Detail label="Description">
                          <Text variant="body" tone={record.description ? 'primary' : 'secondary'}>
                            {record.description || 'No description'}
                          </Text>
                        </Detail>
                      </div>
                    </div>
                  )}

                  <div
                    style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, flexWrap: 'wrap', marginTop: 16 }}
                    onClick={(event) => event.stopPropagation()}
                  >
                    {isEditing ? (
                      <>
                        <Button size="small" onClick={onCancelEditing}>
                          Cancel
                        </Button>
                        <Button size="small" variant="contained" onClick={() => onSave(record.id)}>
                          Save
                        </Button>
                      </>
                    ) : (
                      <>
                        {canViewRecordDetails ? (
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<History sx={{ fontSize: 16 }} />}
                            onClick={() => onOpenHistory(record)}
                          >
                            Open asset
                          </Button>
                        ) : null}
                        {hasSyncConflict && canResolveSyncConflicts ? (
                          <Button size="small" variant="outlined" onClick={() => onResolveSyncConflict(record.id)}>
                            Resolve conflict
                          </Button>
                        ) : null}
                        {canDeleteRecords ? (
                          <Button size="small" variant="outlined" onClick={() => onDelete(record.id)}>
                            Delete
                          </Button>
                        ) : null}
                      </>
                    )}
                  </div>
                </div>
              </motion.div>
          </td>
        </tr>
      ) : null}
    </>
  );
};

export default RecordCard;
