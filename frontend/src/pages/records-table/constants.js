export const SEARCH_PARAMETERS = [
  {
    key: 'status',
    label: 'Status',
    description: 'Host status (active, updated, missing)',
    aliases: ['state'],
    getValue: (record) => record.status
  },
  {
    key: 'source',
    label: 'Source',
    description: 'Network ownership label from IP sources',
    aliases: ['src'],
    getValue: (record) => record.source
  },
  {
    key: 'origin',
    label: 'Origin',
    description: 'How this host entered the inventory',
    aliases: ['record_origin'],
    getValue: (record) => record.origin
  },
  {
    key: 'conflict',
    label: 'Sync conflict',
    description: 'Whether this manual host conflicts with imported DNS data',
    aliases: ['sync_conflict'],
    getValue: (record) => (record.sync_conflict ? 'yes' : 'no')
  },
  {
    key: 'ip',
    label: 'IP address',
    description: 'IP address or subnet',
    aliases: ['ip_address', 'ipaddr'],
    getValue: (record) => record.ip_address
  },
  {
    key: 'owner',
    label: 'App owner',
    description: 'Application owner',
    aliases: ['application_owner', 'app_owner', 'owner'],
    getValue: (record) => record.application_owner
  },
  {
    key: 'maintainer',
    label: 'Maintainer',
    description: 'System maintainer',
    aliases: ['maint'],
    getValue: (record) => record.maintainer
  },
  {
    key: 'domain',
    label: 'Domain name',
    description: 'Domain name contains',
    aliases: ['name', 'hostname', 'dns_name'],
    getValue: (record) => record.name
  },
  {
    key: 'created',
    label: 'Created date',
    description: 'Creation date (YYYY-MM-DD)',
    aliases: ['creation_date', 'date'],
    getValue: (record) => record.creation_date?.split('T')[0]
  },
  {
    key: 'ports',
    label: 'Open ports',
    description: 'Filter by individual port numbers (e.g., 22, 443, 8080)',
    aliases: ['open_ports', 'port'],
    getValue: (record) => record.open_ports
  }
];

export const STATUS_FILTER_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'unchanged', label: 'Active' },
  { value: 'updated', label: 'Updated' },
  { value: 'missing', label: 'Missing' }
];

export const ORIGIN_FILTER_OPTIONS = [
  { value: '', label: 'Any origin' },
  { value: 'automated', label: 'Automated' },
  { value: 'manual', label: 'Manual' }
];

export const RECORDS_HEADERS_GROUPED = [
  '',
  'Host',
  'IP',
  'Status',
  'Origin',
  'Source',
  'Env',
  'Modified',
  ''
];

export const RECORDS_HEADERS_FLAT = [
  '',
  'Host',
  'IP',
  'Status',
  'Origin',
  'Source',
  'App',
  'Env',
  'Modified',
  ''
];

export const INVENTORY_COL_COUNT_GROUPED = RECORDS_HEADERS_GROUPED.length;
export const INVENTORY_COL_COUNT_FLAT = RECORDS_HEADERS_FLAT.length;

/** Pixel widths for `table-layout: fixed`. Host (`auto`) absorbs leftover space. */
export const INVENTORY_COLGROUP_GROUPED = [28, 'auto', 140, 108, 80, 110, 168, 128, 100];
export const INVENTORY_COLGROUP_FLAT = [28, 'auto', 140, 108, 80, 110, 140, 168, 128, 100];

export const INVENTORY_MIN_WIDTH_GROUPED = 1100;
export const INVENTORY_MIN_WIDTH_FLAT = 1220;

export const INVENTORY_CELL = {
  whiteSpace: 'nowrap',
  padding: '8px 12px',
  verticalAlign: 'middle',
  textAlign: 'left',
  overflow: 'hidden',
  textOverflow: 'ellipsis'
};

export const INVENTORY_TABLE = {
  width: '100%',
  borderCollapse: 'collapse',
  tableLayout: 'fixed'
};
