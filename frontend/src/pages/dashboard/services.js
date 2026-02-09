import axios from 'axios';

export const fetchDashboardSources = async ({ canViewPentest, isAdmin }) => {
  const safeGet = async (requestPromise, fallback) => {
    try {
      const response = await requestPromise;
      return response.data ?? fallback;
    } catch (error) {
      return fallback;
    }
  };

  const [records, pentestRecords, ipSourcesPayload] = await Promise.all([
    safeGet(axios.get('/api/records'), []),
    canViewPentest ? safeGet(axios.get('/pentest/records'), []) : Promise.resolve([]),
    isAdmin ? safeGet(axios.get('/ip-sources'), { ip_sources: [] }) : Promise.resolve({ ip_sources: [] })
  ]);

  return {
    records,
    pentestRecords,
    ipSources: ipSourcesPayload?.ip_sources || []
  };
};
