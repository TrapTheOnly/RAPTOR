import axios from 'axios';

export const fetchDashboardSources = async () => {
  const response = await axios.get('/dashboard/data');
  const payload = response.data || {};
  return {
    records: payload.records || [],
    pentestRecords: payload.pentestRecords || [],
    ipSources: payload.ipSources || [],
    findingsSummary: payload.findingsSummary || {
      open: 0,
      closed: 0,
      bySeverity: { critical: 0, high: 0, medium: 0, low: 0, none: 0 },
      weekly: [],
      recent: []
    },
    applications: payload.applications || []
  };
};
