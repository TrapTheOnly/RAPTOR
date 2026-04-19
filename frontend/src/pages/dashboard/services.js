import axios from 'axios';

export const fetchDashboardSources = async () => {
  const response = await axios.get('/dashboard/data');
  const payload = response.data || {};
  return {
    records: payload.records || [],
    pentestRecords: payload.pentestRecords || [],
    ipSources: payload.ipSources || []
  };
};
