export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 64;

export const COMMON_PASSWORDS = new Set([
  'password',
  'password1',
  '123456',
  '12345678',
  '123456789',
  'qwerty',
  'qwerty123',
  'letmein',
  'welcome',
  'admin',
  'admin123',
  'iloveyou',
  'monkey',
  'dragon',
  'football',
  'abc123',
  '111111',
  'trustno1',
  'sunshine',
  'princess',
  'login',
  'qwertyuiop',
  'passw0rd',
  'master',
  'shadow'
]);

export const SETTINGS_NAV_WIDTH = 240;

export const USER_SUBSECTIONS = [
  { key: 'existing', label: 'Existing Users', tabLabel: 'Existing' },
  { key: 'add-domain', label: 'Add LDAP Users', tabLabel: 'LDAP' },
  { key: 'local', label: 'Add Local Users', tabLabel: 'Local' },
  { key: 'service-accounts', label: 'Service Accounts', tabLabel: 'Service accounts' }
];

export const DOMAIN_SUBSECTIONS = [
  { key: 'collectors', label: 'Collectors', tabLabel: 'Collectors', requires: 'collectors' },
  { key: 'cloud', label: 'Cloud DNS', tabLabel: 'Cloud DNS', requires: 'collectors' },
  { key: 'ip-sources', label: 'IP Sources', tabLabel: 'IP Sources', requires: 'ipSources' }
];

export const AI_SCANNER_SUBSECTIONS = [
  { key: 'connections', label: 'Connections', tabLabel: 'Connections' },
  { key: 'local', label: 'Local model', tabLabel: 'Local model' },
  { key: 'policy', label: 'Policy', tabLabel: 'Policy' }
];

export const ROLE_OPTIONS = [
  { value: 'user', label: 'User' },
  { value: 'pentester', label: 'Pentester' },
  { value: 'manager', label: 'Manager' }
];

// Checklist template CRUD stays admin-only in AdminSettings. Do not expose it as an optional
// role permission or move it onto managers.
export const ROLE_METADATA = {
  user: {
    label: 'User',
    description:
      'Default access to records with optional dashboard, pentest dashboard (Security index), and app management. Optional pentest dashboard is not host-notebook access.',
    optionalPermissions: ['view_dashboard', 'view_security_dashboard', 'manage_apps']
  },
  pentester: {
    label: 'Pentester',
    description: 'Security testing access with optional record editing and app management.',
    optionalPermissions: ['view_dashboard', 'modify_records', 'manage_apps']
  },
  manager: {
    label: 'Manager',
    description: 'Full user and pentester capabilities plus admin-level pentest reassignment and record deletion.',
    optionalPermissions: []
  },
  admin: {
    label: 'Admin',
    description: 'Full system access, user management, and configuration control.',
    optionalPermissions: []
  }
};

export const OPTIONAL_PERMISSION_LABELS = {
  view_dashboard: {
    label: 'View dashboard',
    description: 'Allows access to the main dashboard overview.'
  },
  view_security_dashboard: {
    label: 'View pentest dashboard',
    description: 'Allows access to the Security index (/pentest). Does not grant host notebooks or the app workspace.'
  },
  manage_apps: {
    label: 'Manage apps',
    description: 'Create applications and assign domains to them.'
  },
  modify_records: {
    label: 'Modify records',
    description: 'Edit record ownership, ports, and descriptions.'
  }
};
