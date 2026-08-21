import React from 'react';
import {
  Button,
  DataList,
  DataRow,
  EmptyState,
  Field,
  Mono,
  ProviderMark,
  Surface,
  Text
} from '../../../design/primitives';
import { SPACE } from '../../../design/tokens';
import SectionHeader from './SectionHeader';

const SOURCE_MARKS = {
  Cloudflare: 'cloudflare',
  AWS: 'route53',
  Azure: 'azure',
  'Google Cloud': 'gcp',
  'Alibaba Cloud': 'alidns'
};

const IpSourcesSection = ({
  loading,
  sourceTypes,
  ipsBySource,
  selectedSource,
  newSourceName,
  setNewSourceName,
  newIpAddress,
  setNewIpAddress,
  onAddSourceType,
  onSelectSourceType,
  onAddIp,
  onDeleteIp,
  onSubmitChanges
}) => (
  <div>
    <SectionHeader title="IP Sources" />

    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(220px, 320px) minmax(0, 1fr)',
        gap: SPACE.x16,
        alignItems: 'start'
      }}
    >
      <Surface style={{ padding: SPACE.x16 }}>
        <Text as="div" variant="bodyStrong" style={{ marginBottom: SPACE.x12 }}>
          Source groups
        </Text>
        <div style={{ display: 'flex', flexDirection: 'column', gap: SPACE.x12 }}>
          <Field
            label="New source name"
            value={newSourceName}
            onChange={(event) => setNewSourceName(event.target.value)}
          />
          <Button variant="contained" onClick={onAddSourceType} disabled={!newSourceName.trim()}>
            Add source
          </Button>
        </div>
        <div style={{ marginTop: SPACE.x16 }}>
          {sourceTypes.length === 0 ? (
            <Text variant="meta" tone="secondary">
              No sources yet.
            </Text>
          ) : (
            <DataList>
              {sourceTypes.map((source) => (
                <DataRow
                  key={source}
                  id={source}
                  selected={selectedSource === source}
                  onToggle={() => onSelectSourceType(source)}
                  leading={
                    SOURCE_MARKS[source] ? <ProviderMark type={SOURCE_MARKS[source]} size={18} /> : null
                  }
                  title={<Text variant="bodyStrong">{source}</Text>}
                />
              ))}
            </DataList>
          )}
        </div>
      </Surface>

      <Surface style={{ padding: SPACE.x16 }}>
        <Text as="div" variant="bodyStrong" style={{ marginBottom: SPACE.x12 }}>
          IP addresses
        </Text>
        {!selectedSource ? (
          <Text variant="meta" tone="secondary">
            Select a source group to manage IPs.
          </Text>
        ) : (
          <>
            <div style={{ display: 'flex', gap: SPACE.x8, alignItems: 'flex-end', marginBottom: SPACE.x12 }}>
              <Field
                label="Add IP address"
                value={newIpAddress}
                onChange={(event) => setNewIpAddress(event.target.value)}
              />
              <Button variant="contained" onClick={onAddIp}>
                Add
              </Button>
            </div>
            {(ipsBySource[selectedSource] || []).length === 0 ? (
              <EmptyState title="No IPs for this source yet" />
            ) : (
              <DataList>
                {(ipsBySource[selectedSource] || []).map((ip) => (
                  <DataRow
                    key={ip}
                    id={ip}
                    title={<Mono>{ip}</Mono>}
                    trailing={
                      <Button size="small" onClick={() => onDeleteIp(ip)}>
                        Delete
                      </Button>
                    }
                  />
                ))}
              </DataList>
            )}
            <Button
              variant="contained"
              onClick={onSubmitChanges}
              disabled={loading}
              style={{ marginTop: SPACE.x16, width: '100%' }}
            >
              Submit changes
            </Button>
          </>
        )}
      </Surface>
    </div>
  </div>
);

export default IpSourcesSection;
