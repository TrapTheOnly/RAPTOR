import React, { useState } from 'react';
import { Add, DeleteOutline, Language, Save, ShareOutlined } from '@mui/icons-material';
import {
  Button,
  DataList,
  DataRow,
  EmptyState,
  Field,
  Mono,
  Tag,
  Text,
  Toolbar
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';

const METADATA_FIELDS = [
  { key: 'owner', label: 'Business owner', placeholder: 'Team or individual accountable for the app' },
  { key: 'app_lead', label: 'App lead', placeholder: 'Username that always retains environment access' },
  { key: 'data_class', label: 'Data classification', placeholder: 'e.g. Restricted' },
  { key: 'roe_link', label: 'Rules of engagement link', placeholder: 'https://…' },
  { key: 'cookie_domain', label: 'Cookie domain', placeholder: '.example.com' },
  { key: 'idp', label: 'Identity provider', placeholder: 'e.g. Entra ID, Okta' },
  { key: 'token_audience', label: 'Token audience', placeholder: 'API audience / client ID' }
];

const SectionHead = ({ title, hint, actions }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'flex-end',
      gap: 16,
      marginBottom: 16
    }}
  >
    <div>
      <Text as="div" variant="h2">
        {title}
      </Text>
      {hint ? (
        <Text as="p" variant="meta" tone="secondary" style={{ margin: '4px 0 0', maxWidth: 560 }}>
          {hint}
        </Text>
      ) : null}
    </div>
    {actions}
  </div>
);

const ProgramTab = ({
  metadata,
  onMetadataChange,
  onSaveMetadata,
  metadataDirty,
  zones,
  onCreateZone,
  onDeleteZone,
  sharedHosts,
  canManage
}) => {
  const [zoneSuffix, setZoneSuffix] = useState('');
  const [zoneName, setZoneName] = useState('');
  const [zoneError, setZoneError] = useState('');

  const addZone = async () => {
    const suffix = zoneSuffix.trim().toLowerCase().replace(/^\./, '');
    if (!/^[a-z0-9.-]+\.[a-z]{2,}$/.test(suffix)) {
      setZoneError('Enter a domain suffix such as corp.example.com');
      return;
    }
    setZoneError('');
    await onCreateZone({ suffix, display_name: zoneName.trim() || suffix });
    setZoneSuffix('');
    setZoneName('');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x32 }}>
      <section>
        <SectionHead
          title="Application identity"
          hint="Cookie scope, identity provider, and ownership. This is metadata for testers — it does not grant access."
          actions={
            canManage ? (
              <Button
                size="small"
                variant="contained"
                startIcon={<Save />}
                disabled={!metadataDirty}
                onClick={onSaveMetadata}
              >
                {metadataDirty ? 'Save changes' : 'Saved'}
              </Button>
            ) : null
          }
        />
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 16
          }}
        >
          {METADATA_FIELDS.map((field) => (
            <Field
              key={field.key}
              label={field.label}
              placeholder={field.placeholder}
              value={metadata[field.key] || ''}
              disabled={!canManage}
              onChange={(event) => onMetadataChange(field.key, event.target.value)}
            />
          ))}
        </div>
      </section>

      <section>
        <SectionHead
          title="Host domains"
          hint="These DNS suffixes appear as the Host domain filter on the export sheet. Example: keep only hostnames ending in .prod.example.com."
        />
        {canManage ? (
          <Toolbar>
            <Field
              label="Domain suffix"
              placeholder="prod.example.com"
              value={zoneSuffix}
              error={zoneError}
              onChange={(event) => {
                setZoneSuffix(event.target.value);
                setZoneError('');
              }}
              fullWidth={false}
              style={{ width: 240 }}
            />
            <Field
              label="Label (optional)"
              placeholder="Corporate"
              value={zoneName}
              onChange={(event) => setZoneName(event.target.value)}
              fullWidth={false}
              style={{ width: 200 }}
            />
            <Button
              size="small"
              variant="outlined"
              startIcon={<Add />}
              onClick={addZone}
              disabled={!zoneSuffix.trim()}
            >
              Add zone
            </Button>
          </Toolbar>
        ) : null}

        {zones.length === 0 ? (
          <EmptyState
            icon={Language}
            title="No host domains registered"
            hint="Add the DNS suffixes this application lives under. Exports can then keep only hostnames in one of those domains."
          />
        ) : (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {zones.map((zone) => (
              <span key={zone.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                <Tag>
                  {zone.display_name && zone.display_name !== zone.suffix
                    ? `${zone.display_name} · .${zone.suffix}`
                    : `.${zone.suffix}`}
                </Tag>
                {canManage ? (
                  <Button size="small" onClick={() => onDeleteZone(zone.id)} aria-label={`Delete ${zone.suffix}`}>
                    <DeleteOutline sx={{ fontSize: 16 }} />
                  </Button>
                ) : null}
              </span>
            ))}
          </div>
        )}
      </section>

      <section>
        <SectionHead
          title="Shared infrastructure"
          hint="Hosts owned by another application that were explicitly shared with this one. You can attach them to findings as occurrences; their notebook stays with the owner."
        />
        {sharedHosts.length === 0 ? (
          <EmptyState
            icon={ShareOutlined}
            title="Nothing shared with this app"
            hint="When another application shares an SSO or gateway host, it appears here and becomes attachable to your findings."
          />
        ) : (
          <DataList>
            {sharedHosts.map((host) => (
              <DataRow
                key={host.id}
                id={host.id}
                title={<Mono style={{ fontWeight: 600 }}>{host.name}</Mono>}
                meta={
                  <Text as="div" variant="meta" tone="secondary" style={{ marginTop: 4 }}>
                    owned by {host.owner_application_name || `app ${host.owner_application_id}`}
                  </Text>
                }
              />
            ))}
          </DataList>
        )}
      </section>
    </div>
  );
};

export default ProgramTab;
