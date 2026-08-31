import { DataList, DataRow, Tag, Text } from '../../design/primitives';
import { SPACE } from '../../design/tokens';
import { usePalette } from '../../design/usePalette';

const KIND_LABEL = {
  ai_scan: 'AI scan',
  jwt: 'JWT',
  analyze: 'Analyze',
  scanner: 'Scanner'
};

const ACTIVE_STATUS = new Set(['running', 'naming', 'pending', 'queued']);

function formatWhen(value) {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

const EngagementRail = ({ engagements, selectedId, onSelect }) => {
  const palette = usePalette();
  const rows = engagements || [];

  return (
    <aside
      aria-label="Engagements"
      style={{
        width: 300,
        flexShrink: 0,
        borderRight: `1px solid ${palette.line}`,
        display: 'flex',
        flexDirection: 'column',
        minHeight: 560
      }}
    >
      <div style={{ padding: `${SPACE.x12}px ${SPACE.x12}px ${SPACE.x8}px` }}>
        <Text variant="micro" tone="secondary">
          Engagements
        </Text>
      </div>
      {rows.length === 0 ? (
        <div style={{ padding: SPACE.x12 }}>
          <Text variant="meta" tone="secondary">
            Launch an AI scan or send a JWT from Burp. RAPTOR names each job before work starts.
          </Text>
        </div>
      ) : (
        <div style={{ flex: 1, overflowY: 'auto' }}>
          <DataList>
            {rows.map((item) => {
              const selected = item.id === selectedId;
              const kind = KIND_LABEL[item.kind] || item.kind;
              const metaBits = [kind, item.host, formatWhen(item.created_at)].filter(Boolean);
              return (
                <DataRow
                  key={item.id}
                  id={item.id}
                  selected={selected}
                  onToggle={() => onSelect(item.id)}
                  title={
                    <Text
                      variant="bodyStrong"
                      style={{
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}
                    >
                      {item.title || 'Naming…'}
                    </Text>
                  }
                  meta={
                    <Text variant="meta" tone="secondary" style={{ display: 'block' }}>
                      {metaBits.join(' · ')}
                    </Text>
                  }
                  trailing={
                    <Tag emphasized={ACTIVE_STATUS.has(item.status)}>{item.status}</Tag>
                  }
                />
              );
            })}
          </DataList>
        </div>
      )}
    </aside>
  );
};

export default EngagementRail;
