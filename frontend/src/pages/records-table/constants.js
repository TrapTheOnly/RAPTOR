export const SEARCH_PARAMETERS = [
  {
    key: 'status',
    label: 'Status',
    icon: '📊',
    description: 'Record status (active, updated, missing)',
    aliases: ['state'],
    getValue: (record) => record.status
  },
  {
    key: 'source',
    label: 'Source',
    icon: '🏷️',
    description: 'Data source (Production, External, etc.)',
    aliases: ['src'],
    getValue: (record) => record.source
  },
  {
    key: 'origin',
    label: 'Origin',
    icon: '🧭',
    description: 'How this record entered the registry',
    aliases: ['record_origin'],
    getValue: (record) => record.origin
  },
  {
    key: 'conflict',
    label: 'Sync Conflict',
    icon: '⚠️',
    description: 'Whether this manual record conflicts with imported DNS data',
    aliases: ['sync_conflict'],
    getValue: (record) => (record.sync_conflict ? 'yes' : 'no')
  },
  {
    key: 'ip',
    label: 'IP Address',
    icon: '🌐',
    description: 'IP address or subnet',
    aliases: ['ip_address', 'ipaddr'],
    getValue: (record) => record.ip_address
  },
  {
    key: 'owner',
    label: 'App Owner',
    icon: '👤',
    description: 'Application owner',
    aliases: ['application_owner', 'app_owner', 'owner'],
    getValue: (record) => record.application_owner
  },
  {
    key: 'maintainer',
    label: 'Maintainer',
    icon: '🔧',
    description: 'System maintainer',
    aliases: ['maint'],
    getValue: (record) => record.maintainer
  },
  {
    key: 'domain',
    label: 'Domain Name',
    icon: '🌍',
    description: 'Domain name contains',
    aliases: ['name', 'hostname', 'dns_name'],
    getValue: (record) => record.name
  },
  {
    key: 'created',
    label: 'Created Date',
    icon: '📅',
    description: 'Creation date (YYYY-MM-DD)',
    aliases: ['creation_date', 'date'],
    getValue: (record) => record.creation_date?.split('T')[0]
  },
  {
    key: 'ports',
    label: 'Open Ports',
    icon: '🔌',
    description: 'Filter by individual port numbers (e.g., 22, 443, 8080)',
    aliases: ['open_ports', 'port'],
    getValue: (record) => record.open_ports
  }
];

export const SOURCE_COLORS = {
  Production: '#4CAF50',
  External: '#2196F3',
  Development: '#FF9800',
  Testing: '#9C27B0',
  Other: '#666666'
};
