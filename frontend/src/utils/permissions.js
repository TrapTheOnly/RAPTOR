export const ROLE_DEFAULT_PERMISSIONS = {
  user: ['view_records', 'modify_records', 'view_record_details', 'export_records'],
  pentester: [
    'view_records',
    'view_security_dashboard',
    'view_record_details',
    'export_records',
    'view_pentest_page',
    'modify_pentests',
    'export_pentests'
  ],
  manager: [
    'view_settings',
    'view_dashboard',
    'view_records',
    'view_security_dashboard',
    'create_manual_records',
    'modify_records',
    'view_record_details',
    'export_records',
    'manage_ip_sources',
    'manage_vuln_categories',
    'manage_report_templates',
    'manage_apps',
    'view_pentest_page',
    'modify_pentests',
    'export_pentests',
    'reassign_pentests_admin',
    'delete_records',
    'modify_others_pentests_admin'
  ],
  admin: ['*']
};

export const hasPermission = (userRole, userPermissions, permission) => {
  const normalizedRole = String(userRole || '').trim().toLowerCase();
  const roleDefaults = ROLE_DEFAULT_PERMISSIONS[normalizedRole] || [];
  if (roleDefaults.includes('*') || roleDefaults.includes(permission)) {
    return true;
  }
  return Array.isArray(userPermissions) && userPermissions.includes(permission);
};
