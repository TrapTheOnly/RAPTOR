import {
  RECENT_ACTIVITY_LIMIT,
  RECENT_WINDOW_DAYS,
  TESTER_WORKLOAD_LIMIT,
  TOP_RISK_LIMIT,
  TREND_MONTHS
} from './constants';

const DAY_MS = 24 * 60 * 60 * 1000;

const parseDateValue = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

const withinLastDays = (value, days, now) => {
  const date = parseDateValue(value);
  if (!date) return false;
  return date.getTime() >= now.getTime() - days * DAY_MS;
};

const parseVulnerabilities = (rawValue) => {
  if (!rawValue) return [];
  if (Array.isArray(rawValue)) return rawValue;
  if (typeof rawValue === 'string') {
    try {
      const parsed = JSON.parse(rawValue);
      return Array.isArray(parsed) ? parsed : [];
    } catch (error) {
      return [];
    }
  }
  return [];
};

const getVulnerabilityCount = (record) => {
  const parsed = parseVulnerabilities(record.vulnerabilities);
  if (parsed.length > 0) return parsed.length;
  return record.vulnerable === 1 ? 1 : 0;
};

const buildMonthlyBuckets = (months, now) => {
  const buckets = [];
  for (let offset = months - 1; offset >= 0; offset -= 1) {
    const start = new Date(now.getFullYear(), now.getMonth() - offset, 1);
    const end = new Date(now.getFullYear(), now.getMonth() - offset + 1, 0, 23, 59, 59, 999);
    buckets.push({
      key: `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}`,
      label: start.toLocaleString('en-US', { month: 'short' }),
      start,
      end
    });
  }
  return buckets;
};

const getBucketIndex = (date, buckets) =>
  buckets.findIndex((bucket) => date >= bucket.start && date <= bucket.end);

export const buildTrendData = (pentestRecords, now = new Date()) => {
  const buckets = buildMonthlyBuckets(TREND_MONTHS, now);
  const started = Array(buckets.length).fill(0);
  const completed = Array(buckets.length).fill(0);
  const detected = Array(buckets.length).fill(0);
  const resolved = Array(buckets.length).fill(0);

  pentestRecords.forEach((record) => {
    const startDate = parseDateValue(record.test_start_date);
    const endDate = parseDateValue(record.test_end_date);
    const vulnerabilityCount = getVulnerabilityCount(record);

    if (startDate) {
      const index = getBucketIndex(startDate, buckets);
      if (index >= 0) started[index] += 1;
    }

    if (record.status === 'Completed' && endDate) {
      const index = getBucketIndex(endDate, buckets);
      if (index >= 0) completed[index] += 1;
    }

    if (vulnerabilityCount > 0) {
      const detectedDate = endDate || startDate;
      if (detectedDate) {
        const index = getBucketIndex(detectedDate, buckets);
        if (index >= 0) detected[index] += vulnerabilityCount;
      }

      if (record.vulnerability_fixed === 1) {
        const resolvedDate = endDate || startDate;
        if (resolvedDate) {
          const index = getBucketIndex(resolvedDate, buckets);
          if (index >= 0) resolved[index] += vulnerabilityCount;
        }
      }
    }
  });

  return {
    labels: buckets.map((bucket) => bucket.label),
    testSeries: {
      started,
      completed
    },
    vulnerabilitySeries: {
      detected,
      resolved
    }
  };
};

export const buildKpis = ({ records, pentestRecords, ipSources }, now = new Date()) => {
  const totalAssets = records.length;
  const startedTests = pentestRecords.filter((record) =>
    ['In Progress', 'Completed'].includes(record.status)
  ).length;
  const inProgressTests = pentestRecords.filter(
    (record) => record.status === 'In Progress'
  ).length;
  const completedTests = pentestRecords.filter(
    (record) => record.status === 'Completed'
  ).length;

  const vulnerableAssets = pentestRecords.filter(
    (record) => record.vulnerable === 1
  ).length;
  const openRiskAssets = pentestRecords.filter(
    (record) => record.vulnerable === 1 && record.vulnerability_fixed !== 1
  ).length;
  const fixedAssets = pentestRecords.filter(
    (record) => record.vulnerability_fixed === 1
  ).length;

  const startedLast30d = pentestRecords.filter((record) =>
    withinLastDays(record.test_start_date, RECENT_WINDOW_DAYS, now)
  ).length;
  const completedLast30d = pentestRecords.filter(
    (record) =>
      record.status === 'Completed' &&
      withinLastDays(record.test_end_date, RECENT_WINDOW_DAYS, now)
  ).length;

  const newDetectedVulns30d = pentestRecords.reduce((acc, record) => {
    const vulnerabilityCount = getVulnerabilityCount(record);
    if (vulnerabilityCount <= 0) return acc;

    const detectionDate = record.test_end_date || record.test_start_date;
    if (!withinLastDays(detectionDate, RECENT_WINDOW_DAYS, now)) return acc;
    return acc + vulnerabilityCount;
  }, 0);

  const unresolvedVulnerabilityIndicators = pentestRecords.reduce((acc, record) => {
    if (record.vulnerability_fixed === 1) return acc;
    return acc + getVulnerabilityCount(record);
  }, 0);

  const cycleDurations = pentestRecords
    .map((record) => {
      const startDate = parseDateValue(record.test_start_date);
      const endDate = parseDateValue(record.test_end_date);
      if (!startDate || !endDate) return null;
      const duration = (endDate.getTime() - startDate.getTime()) / DAY_MS;
      return duration >= 0 ? duration : null;
    })
    .filter((duration) => duration !== null);

  const averageCycleDays =
    cycleDurations.length > 0
      ? Math.round((cycleDurations.reduce((acc, value) => acc + value, 0) / cycleDurations.length) * 10) /
        10
      : 0;

  const coveragePct =
    totalAssets > 0 ? Math.round((startedTests / totalAssets) * 100) : 0;
  const fixRatePct =
    vulnerableAssets > 0 ? Math.round((fixedAssets / vulnerableAssets) * 100) : 0;

  return {
    totalAssets,
    startedTests,
    inProgressTests,
    completedTests,
    vulnerableAssets,
    openRiskAssets,
    fixedAssets,
    startedLast30d,
    completedLast30d,
    newDetectedVulns30d,
    unresolvedVulnerabilityIndicators,
    averageCycleDays,
    coveragePct,
    fixRatePct,
    ipSourceCount: [...new Set(ipSources.map((item) => item.source_name))].length
  };
};

export const buildRecentActivity = (
  { records, pentestRecords },
  now = new Date(),
  limit = RECENT_ACTIVITY_LIMIT
) => {
  const events = [];

  pentestRecords.forEach((record) => {
    const startDate = parseDateValue(record.test_start_date);
    const endDate = parseDateValue(record.test_end_date);
    const vulnerabilityCount = getVulnerabilityCount(record);
    const tester = (record.tested_by || 'Unassigned').trim() || 'Unassigned';

    if (startDate && withinLastDays(startDate, RECENT_WINDOW_DAYS, now)) {
      events.push({
        id: `start-${record.recordId}-${startDate.getTime()}`,
        type: 'test_started',
        title: 'Test started',
        subtitle: `${record.name} • ${tester}`,
        timestamp: startDate.getTime()
      });
    }

    if (record.status === 'Completed' && endDate && withinLastDays(endDate, RECENT_WINDOW_DAYS, now)) {
      events.push({
        id: `complete-${record.recordId}-${endDate.getTime()}`,
        type: 'test_completed',
        title: 'Test completed',
        subtitle: `${record.name} • ${record.vulnerable === 1 ? 'Vulnerable' : 'No findings'}`,
        timestamp: endDate.getTime()
      });
    }

    if (vulnerabilityCount > 0) {
      const detectionDate = endDate || startDate;
      if (detectionDate && withinLastDays(detectionDate, RECENT_WINDOW_DAYS, now)) {
        events.push({
          id: `vuln-${record.recordId}-${detectionDate.getTime()}`,
          type: 'vuln_detected',
          title: 'New vulnerabilities detected',
          subtitle: `${record.name} • ${vulnerabilityCount} finding${vulnerabilityCount === 1 ? '' : 's'}`,
          timestamp: detectionDate.getTime()
        });
      }
    }
  });

  records.forEach((record) => {
    if (!['updated', 'missing'].includes(record.status)) return;
    const changeDate = parseDateValue(record.last_modification_date);
    if (!changeDate || !withinLastDays(changeDate, RECENT_WINDOW_DAYS, now)) return;

    events.push({
      id: `scope-${record.id}-${changeDate.getTime()}`,
      type: record.status === 'missing' ? 'scope_missing' : 'scope_updated',
      title: record.status === 'missing' ? 'Asset marked missing' : 'Scope change detected',
      subtitle: record.name,
      timestamp: changeDate.getTime()
    });
  });

  return events.sort((left, right) => right.timestamp - left.timestamp).slice(0, limit);
};

export const buildTopRiskAssets = (pentestRecords, limit = TOP_RISK_LIMIT) =>
  pentestRecords
    .map((record) => {
      const vulnerabilityCount = getVulnerabilityCount(record);
      const openRisk = record.vulnerable === 1 && record.vulnerability_fixed !== 1;
      const riskScore =
        vulnerabilityCount * 3 +
        (openRisk ? 5 : 0) +
        (record.status === 'In Progress' ? 2 : 0) +
        (record.status === 'Completed' ? 1 : 0);

      return {
        key: `${record.recordId}-${record.name}`,
        name: record.name,
        source: record.source || 'N/A',
        testedBy: record.tested_by || 'Unassigned',
        status: record.status || 'Not Started',
        vulnerabilityCount,
        openRisk,
        riskScore
      };
    })
    .filter((asset) => asset.riskScore > 0)
    .sort((left, right) => right.riskScore - left.riskScore)
    .slice(0, limit);

export const buildTesterWorkload = (
  pentestRecords,
  limit = TESTER_WORKLOAD_LIMIT
) => {
  const grouped = pentestRecords.reduce((acc, record) => {
    const tester = (record.tested_by || 'Unassigned').trim() || 'Unassigned';
    if (!acc[tester]) {
      acc[tester] = {
        tester,
        total: 0,
        inProgress: 0,
        completed: 0,
        openRiskAssets: 0,
        vulnerabilityIndicators: 0
      };
    }

    acc[tester].total += 1;
    if (record.status === 'In Progress') acc[tester].inProgress += 1;
    if (record.status === 'Completed') acc[tester].completed += 1;
    if (record.vulnerable === 1 && record.vulnerability_fixed !== 1) {
      acc[tester].openRiskAssets += 1;
    }
    acc[tester].vulnerabilityIndicators += getVulnerabilityCount(record);
    return acc;
  }, {});

  return Object.values(grouped)
    .sort((left, right) => {
      if (right.openRiskAssets !== left.openRiskAssets) {
        return right.openRiskAssets - left.openRiskAssets;
      }
      if (right.inProgress !== left.inProgress) {
        return right.inProgress - left.inProgress;
      }
      return right.total - left.total;
    })
    .slice(0, limit);
};

export const formatActivityTimestamp = (timestamp) => {
  if (!timestamp) return 'N/A';
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) return 'N/A';

  const diffMs = Date.now() - date.getTime();
  if (diffMs < 60 * 60 * 1000) {
    const mins = Math.max(1, Math.floor(diffMs / (60 * 1000)));
    return `${mins}m ago`;
  }
  if (diffMs < 24 * 60 * 60 * 1000) {
    const hours = Math.max(1, Math.floor(diffMs / (60 * 60 * 1000)));
    return `${hours}h ago`;
  }
  if (diffMs < 7 * DAY_MS) {
    const days = Math.max(1, Math.floor(diffMs / DAY_MS));
    return `${days}d ago`;
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

export const buildDashboardViewModel = ({ records, pentestRecords, ipSources }) => {
  const now = new Date();
  return {
    kpis: buildKpis({ records, pentestRecords, ipSources }, now),
    trends: buildTrendData(pentestRecords, now),
    recentActivity: buildRecentActivity({ records, pentestRecords }, now),
    topRiskAssets: buildTopRiskAssets(pentestRecords),
    testerWorkload: buildTesterWorkload(pentestRecords),
    generatedAt: now.toISOString()
  };
};
