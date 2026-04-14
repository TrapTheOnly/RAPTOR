import axios from 'axios';

export const getSessionStatus = () => axios.get('/session-status');

export const getRecords = () => axios.get('/api/records');
export const createManualRecord = (payload) => axios.post('/api/records', payload);

export const getApps = () => axios.get('/api/apps');

export const createApp = (name) => axios.post('/api/apps', { name });

export const renameApp = (appId, name) => axios.put(`/api/apps/${appId}`, { name });

export const deleteAppById = (appId) => axios.delete(`/api/apps/${appId}`);

export const updateRecordById = (recordId, payload) =>
  axios.post(`/api/records/${recordId}`, payload);

export const resolveSyncConflictById = (recordId) =>
  axios.post(`/api/records/${recordId}/resolve-sync-conflict`);

export const deleteRecordById = (recordId) => axios.delete(`/api/records/${recordId}`);
