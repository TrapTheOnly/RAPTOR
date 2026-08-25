import {
  RECENT_ACTIVITY_LIMIT,
  RECENT_WINDOW_DAYS,
  STARTED_STATUSES,
  STALE_DAYS
} from './constants';

const DAY_MS = 24 * 60 * 60 * 1000;

export const parseDateValue = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
};

const withinLastDays = (value, days, now) => {
  const date = parseDateValue(value);
  if (!date) return false;
  return date.getTime() >= now.getTime() - days * DAY_MS;
};

const recordIdOf = (record) => record.recordId ?? record.recordid ?? record.id;
const applicationIdOf = (record) =>
  record.applicationId ?? record.applicationid ?? record.application_id ?? null;
const testerOf = (record) => {
  const raw = String(record.tested_by ?? record.testedBy ?? '').trim();
  return raw || 'Unassigned';
};

const pentestStatus = (record) => String(record.status || 'Not Started');
const isStarted = (record) => STARTED_STATUSES.includes(pentestStatus(record));
const isCompleted = (record) => pentestStatus(record) === 'Completed';
const findingCountOf = (record) => Number(record.finding_count ?? record.findingCount ?? 0) || 0;

export const buildKpis = (
  { pentestRecords = [], findingsSummary = {} },
  now = new Date()
) => {
  const neverTested = pentestRecords.filter((record) => !isStarted(record)).length;
  const stale = pentestRecords.filter((record) => {
    if (!isCompleted(record)) return false;
    const end = parseDateValue(record.test_end_date);
    if (!end) return true;
    return now.getTime() - end.getTime() > STALE_DAYS * DAY_MS;
  }).length;
  const unassigned = pentestRecords.filter((record) => testerOf(record) === 'Unassigned').length;
  const weekly = findingsSummary.weekly || [];
  const lastFive = weekly.slice(-5);
  const openedLast30d = lastFive.reduce((sum, week) => sum + Number(week.opened || 0), 0);
  const closedLast30d = lastFive.reduce((sum, week) => sum + Number(week.closed || 0), 0);
  const bySeverity = findingsSummary.bySeverity || {};
  const criticalHigh = Number(bySeverity.critical || 0) + Number(bySeverity.high || 0);

  return {
    openFindings: Number(findingsSummary.open || 0),
    closedFindings: Number(findingsSummary.closed || 0),
    criticalHigh,
    neverTested,
    stale,
    unassigned,
    openedLast30d,
    closedLast30d,
    inProgress: pentestRecords.filter((record) => pentestStatus(record) === 'In Progress').length
  };
};

export const buildCoverageGaps = (pentestRecords = [], now = new Date()) => {
  const neverTested = [];
  const stale = [];
  pentestRecords.forEach((record) => {
    const item = {
      id: recordIdOf(record),
      name: record.name,
      source: record.source || 'N/A',
      applicationId: applicationIdOf(record),
      status: pentestStatus(record),
      tester: testerOf(record),
      lastTested: parseDateValue(record.test_end_date)
    };
    if (!isStarted(record)) {
      neverTested.push(item);
      return;
    }
    if (isCompleted(record)) {
      const end = item.lastTested;
      if (!end || now.getTime() - end.getTime() > STALE_DAYS * DAY_MS) {
        stale.push({ ...item, kind: 'stale' });
      }
    }
  });
  neverTested.sort((left, right) => String(left.name).localeCompare(String(right.name)));
  stale.sort((left, right) => {
    const leftTime = left.lastTested ? left.lastTested.getTime() : 0;
    const rightTime = right.lastTested ? right.lastTested.getTime() : 0;
    return leftTime - rightTime;
  });
  return {
    neverTested,
    stale,
    neverTestedTotal: neverTested.length,
    staleTotal: stale.length
  };
};

export const buildAppsAtRisk = (applications = []) =>
  [...applications]
    .map((app) => ({
      id: app.id,
      name: app.name,
      openFindingCount: Number(app.open_finding_count || 0),
      inScopeCount: Number(app.in_scope_count || 0),
      startedCount: Number(app.started_count || 0)
    }))
    .filter((app) => app.openFindingCount > 0 || app.inScopeCount > app.startedCount)
    .sort((left, right) => {
      if (right.openFindingCount !== left.openFindingCount) {
        return right.openFindingCount - left.openFindingCount;
      }
      const leftGap = left.inScopeCount - left.startedCount;
      const rightGap = right.inScopeCount - right.startedCount;
      return rightGap - leftGap;
    });

export const buildTesterWorkload = (pentestRecords = []) => {
  const grouped = pentestRecords.reduce((acc, record) => {
    const tester = testerOf(record);
    if (tester === 'Unassigned') return acc;
    if (!acc[tester]) {
      acc[tester] = {
        tester,
        total: 0,
        inProgress: 0,
        completed: 0,
        openFindings: 0
      };
    }
    acc[tester].total += 1;
    if (pentestStatus(record) === 'In Progress') acc[tester].inProgress += 1;
    if (isCompleted(record)) acc[tester].completed += 1;
    if (!(isCompleted(record) && Number(record.vulnerability_fixed) === 1)) {
      acc[tester].openFindings += findingCountOf(record);
    }
    return acc;
  }, {});

  return Object.values(grouped).sort((left, right) => {
    if (right.openFindings !== left.openFindings) return right.openFindings - left.openFindings;
    if (right.inProgress !== left.inProgress) return right.inProgress - left.inProgress;
    return right.total - left.total;
  });
};

export const buildRecentActivity = (
  { records = [], pentestRecords = [], findingsSummary = {} },
  now = new Date(),
  limit = RECENT_ACTIVITY_LIMIT
) => {
  const events = [];

  (findingsSummary.recent || []).forEach((finding) => {
    const created = parseDateValue(finding.createdAt);
    if (!created || !withinLastDays(finding.createdAt, RECENT_WINDOW_DAYS, now)) return;
    events.push({
      id: `finding-${finding.id}`,
      type: 'finding_filed',
      title: finding.title || 'Finding filed',
      subtitle: finding.status || 'open',
      timestamp: created.getTime(),
      applicationId: finding.applicationId,
      findingId: finding.id
    });
  });

  pentestRecords.forEach((record) => {
    const startDate = parseDateValue(record.test_start_date);
    const endDate = parseDateValue(record.test_end_date);
    const id = recordIdOf(record);
    const tester = testerOf(record);

    if (startDate && withinLastDays(record.test_start_date, RECENT_WINDOW_DAYS, now)) {
      events.push({
        id: `start-${id}-${startDate.getTime()}`,
        type: 'test_started',
        title: 'Test started',
        subtitle: `${record.name} • ${tester}`,
        timestamp: startDate.getTime(),
        recordId: id,
        applicationId: applicationIdOf(record)
      });
    }

    if (isCompleted(record) && endDate && withinLastDays(record.test_end_date, RECENT_WINDOW_DAYS, now)) {
      events.push({
        id: `complete-${id}-${endDate.getTime()}`,
        type: 'test_completed',
        title: 'Test completed',
        subtitle: record.name,
        timestamp: endDate.getTime(),
        recordId: id,
        applicationId: applicationIdOf(record)
      });
    }
  });

  records.forEach((record) => {
    if (!['updated', 'missing'].includes(record.status)) return;
    const changeDate = parseDateValue(record.last_modification_date);
    if (!changeDate || !withinLastDays(record.last_modification_date, RECENT_WINDOW_DAYS, now)) return;
    events.push({
      id: `scope-${record.id}-${changeDate.getTime()}`,
      type: record.status === 'missing' ? 'scope_missing' : 'scope_updated',
      title: record.status === 'missing' ? 'Asset marked missing' : 'Scope change detected',
      subtitle: record.name,
      timestamp: changeDate.getTime(),
      recordId: record.id,
      applicationId: applicationIdOf(record)
    });
  });

  return events.sort((left, right) => right.timestamp - left.timestamp).slice(0, limit);
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

export const formatRelativeAge = (date) => {
  if (!date) return 'unknown';
  const diffMs = Date.now() - date.getTime();
  if (diffMs < 7 * DAY_MS) {
    const days = Math.max(1, Math.floor(diffMs / DAY_MS));
    return `${days}d ago`;
  }
  const weeks = Math.max(1, Math.floor(diffMs / (7 * DAY_MS)));
  if (weeks < 8) return `${weeks}w ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

export const buildDashboardViewModel = (sourceData, now = new Date()) => {
  const records = sourceData.records || [];
  const pentestRecords = sourceData.pentestRecords || [];
  const findingsSummary = sourceData.findingsSummary || {
    open: 0,
    closed: 0,
    bySeverity: { critical: 0, high: 0, medium: 0, low: 0, none: 0 },
    weekly: [],
    recent: []
  };
  const applications = sourceData.applications || [];

  return {
    kpis: buildKpis({ pentestRecords, findingsSummary }, now),
    weekly: findingsSummary.weekly || [],
    bySeverity: findingsSummary.bySeverity || {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
      none: 0
    },
    coverageGaps: buildCoverageGaps(pentestRecords, now),
    appsAtRisk: buildAppsAtRisk(applications),
    testerWorkload: buildTesterWorkload(pentestRecords),
    recentActivity: buildRecentActivity({ records, pentestRecords, findingsSummary }, now),
    recentFindings: findingsSummary.recent || [],
    generatedAt: now.toISOString()
  };
};
