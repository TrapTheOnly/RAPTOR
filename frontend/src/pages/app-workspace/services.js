import axios from 'axios';

export const getApps = () => axios.get('/api/apps');

export const getApp = (appId) => axios.get(`/api/apps/${appId}`);

export const updateApp = (appId, payload) => axios.put(`/api/apps/${appId}`, payload);

export const getEnvironments = (appId) => axios.get(`/api/apps/${appId}/environments`);

export const createEnvironment = (appId, payload) =>
  axios.post(`/api/apps/${appId}/environments`, payload);

export const updateEnvironment = (appId, envId, payload) =>
  axios.put(`/api/apps/${appId}/environments/${envId}`, payload);

export const deleteEnvironment = (appId, envId) =>
  axios.delete(`/api/apps/${appId}/environments/${envId}`);

export const assignHosts = (appId, payload) => axios.post(`/api/apps/${appId}/hosts/assign`, payload);

export const assignHostTesters = (appId, payload) =>
  axios.post(`/api/apps/${appId}/hosts/assign-tester`, payload);

export const claimWaveHosts = (appId, waveId, payload) =>
  axios.post(`/api/apps/${appId}/waves/${waveId}/hosts/claim`, payload);

export const listAppHosts = (appId, params) => axios.get(`/api/apps/${appId}/hosts`, { params });

export const searchHosts = (params) => axios.get('/api/hosts/search', { params });

export const listAppFindings = (appId, params) => axios.get(`/api/apps/${appId}/findings`, { params });

export const createAppFinding = (appId, payload) => axios.post(`/api/apps/${appId}/findings`, payload);

export const getFinding = (findingId) => axios.get(`/api/findings/${findingId}`);

export const patchFinding = (findingId, payload) => axios.patch(`/api/findings/${findingId}`, payload);

export const addFindingOccurrences = (findingId, payload) =>
  axios.post(`/api/findings/${findingId}/occurrences`, payload);

export const patchOccurrence = (findingId, recordId, payload) =>
  axios.patch(`/api/findings/${findingId}/occurrences/${recordId}`, payload);

export const bulkSetOccurrenceStatus = (appId, payload) =>
  axios.post(`/api/apps/${appId}/occurrences/bulk-status`, payload);

export const mergeFindings = (findingId, payload) => axios.post(`/api/findings/${findingId}/merge`, payload);

export const promoteFinding = (findingId, payload) => axios.post(`/api/findings/${findingId}/promote`, payload);

export const previewAppReport = (appId, payload) =>
  axios.post(`/api/apps/${appId}/generate-report`, { ...payload, preview: true });

export const generateAppReport = (appId, payload) =>
  axios.post(`/api/apps/${appId}/generate-report`, payload);

export const generateEnvReport = (appId, envId, payload) =>
  axios.post(`/api/apps/${appId}/environments/${envId}/generate-report`, payload);

export const downloadReportExport = (exportId) =>
  axios.get(`/api/report-exports/${exportId}`, { responseType: 'blob' });

export const verifyReportExport = (exportId) => axios.get(`/api/report-exports/${exportId}/verify`);

export const listWaves = (appId) => axios.get(`/api/apps/${appId}/waves`);

export const getWave = (appId, waveId) => axios.get(`/api/apps/${appId}/waves/${waveId}`);

export const launchWaveScan = (appId, waveId, payload = {}) =>
  axios.post(`/api/apps/${appId}/waves/${waveId}/launch-scan`, payload);

export const resetWaveScan = (appId, waveId) =>
  axios.post(`/api/apps/${appId}/waves/${waveId}/reset-scan`);

export const stopWaveScan = (appId, waveId) =>
  axios.post(`/api/apps/${appId}/waves/${waveId}/stop-scan`);

export const putWaveMembers = (appId, waveId, payload) =>
  axios.put(`/api/apps/${appId}/waves/${waveId}/members`, payload);

export const createWave = (appId, payload) => axios.post(`/api/apps/${appId}/waves`, payload);

export const closeWave = (appId, waveId) => axios.post(`/api/apps/${appId}/waves/${waveId}/close`);

export const startWave = (appId, waveId) => axios.post(`/api/apps/${appId}/waves/${waveId}/start`);

export const putWaveEnvironments = (appId, waveId, payload) =>
  axios.put(`/api/apps/${appId}/waves/${waveId}/environments`, payload);

export const setWaveHostScope = (appId, waveId, payload) =>
  axios.post(`/api/apps/${appId}/waves/${waveId}/hosts/scope`, payload);

export const deleteWave = (appId, waveId) => axios.delete(`/api/apps/${appId}/waves/${waveId}`);

export const getEnvAcl = (appId, envId) => axios.get(`/api/apps/${appId}/environments/${envId}/acl`);

export const putEnvAcl = (appId, envId, payload) =>
  axios.put(`/api/apps/${appId}/environments/${envId}/acl`, payload);

export const getEnvChecklists = (appId, envId) =>
  axios.get(`/api/apps/${appId}/environments/${envId}/checklists`);

export const putEnvChecklists = (appId, envId, payload) =>
  axios.put(`/api/apps/${appId}/environments/${envId}/checklists`, payload);

export const listDnsZones = (appId) =>
  axios.get('/api/dns-zones', { params: appId ? { application_id: appId } : {} });

export const createDnsZone = (payload) => axios.post('/api/dns-zones', payload);

export const deleteDnsZone = (zoneId) => axios.delete(`/api/dns-zones/${zoneId}`);

export const shareHost = (appId, recordId, payload) =>
  axios.post(`/api/apps/${appId}/hosts/${recordId}/share`, payload);

export const listSharedHosts = (appId) => axios.get(`/api/apps/${appId}/shared-hosts`);

export const fetchChecklistTemplates = () => axios.get('/checklist-templates');

export const fetchReportTemplates = () => axios.get('/report-templates');

export const fetchPentestUsers = () => axios.get('/pentest_users');
