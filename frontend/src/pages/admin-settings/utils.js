import Papa from 'papaparse';
import { ROLE_METADATA } from './constants';

export const getRoleMeta = (roleKey) => ROLE_METADATA[roleKey] || ROLE_METADATA.user;

export const getOptionalPermissions = (roleKey) => getRoleMeta(roleKey).optionalPermissions || [];

export const normalizeOptionalPermissions = (roleKey, permissions = []) => {
  const allowed = new Set(getOptionalPermissions(roleKey));
  return permissions.filter((permission) => allowed.has(permission));
};

export const buildResetSummary = (data) => ({
  total: data.length,
  completed: data.filter((record) => record.status === 'Completed').length,
  inProgress: data.filter((record) => record.status === 'In Progress').length,
  notStarted: data.filter((record) => !record.status || record.status === 'Not Started').length,
  vulnerable: data.filter((record) => record.vulnerable === 1).length,
  fixed: data.filter((record) => record.vulnerability_fixed === 1).length,
  open: data.filter((record) => record.vulnerable === 1 && record.vulnerability_fixed === 0).length,
  reports: data.filter((record) => record.report_file).length
});

export const buildResetCsv = (data) =>
  Papa.unparse(
    data.map((item) => ({
      'Target Name': item.name,
      'IP Address': item.ip_address,
      Source: item.source,
      Status: item.status,
      Vulnerable: item.vulnerable === 1 ? 'Yes' : 'No',
      'Tested By': item.tested_by,
      'Start Date': item.test_start_date,
      'End Date': item.test_end_date,
      Fixed: item.vulnerability_fixed === 1 ? 'Yes' : 'No',
      'Service Desk': item.service_desk_link,
      Report: item.report_file ? 'Yes' : 'No'
    }))
  );
