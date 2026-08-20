import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert } from '@mui/material';
import {
  Button,
  MetricStrip,
  Page,
  PageHeader,
  Progress,
  Tag
} from '../design/primitives';
import { SPACE } from '../design/tokens';
import { hasPermission as hasRolePermission } from '../utils/permissions';
import { fetchDashboardSources } from './dashboard/services';
import { buildDashboardViewModel } from './dashboard/utils';
import { DEFAULT_LAYOUT, loadLayout, saveLayout } from './dashboard/layout';
import { ArrangeGrid } from './dashboard/components/ArrangeGrid';
import TrendWidget from './dashboard/components/TrendWidget';
import SeverityWidget from './dashboard/components/SeverityWidget';
import CoverageGapsWidget from './dashboard/components/CoverageGapsWidget';
import AppsAtRiskWidget from './dashboard/components/AppsAtRiskWidget';
import TesterWorkloadWidget from './dashboard/components/TesterWorkloadWidget';
import RecentActivityWidget from './dashboard/components/RecentActivityWidget';

const EMPTY_VIEW_MODEL = {
  kpis: {
    openFindings: 0,
    closedFindings: 0,
    criticalHigh: 0,
    neverTested: 0,
    stale: 0,
    unassigned: 0,
    openedLast30d: 0,
    closedLast30d: 0,
    inProgress: 0
  },
  weekly: [],
  bySeverity: { critical: 0, high: 0, medium: 0, low: 0, none: 0 },
  coverageGaps: { neverTested: [], stale: [], neverTestedTotal: 0, staleTotal: 0 },
  appsAtRisk: [],
  testerWorkload: [],
  recentActivity: [],
  recentFindings: [],
  generatedAt: null
};

const Dashboard = ({ username = '', userRole, userPermissions = [] }) => {
  const navigate = useNavigate();
  const [viewModel, setViewModel] = useState(EMPTY_VIEW_MODEL);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [arranging, setArranging] = useState(false);
  const [layout, setLayout] = useState(() => loadLayout(username));

  const canViewSecurity = hasRolePermission(userRole, userPermissions, 'view_security_dashboard');
  const canViewRecords = hasRolePermission(userRole, userPermissions, 'view_records');
  const canViewRecordDetails = hasRolePermission(userRole, userPermissions, 'view_record_details');
  const canViewPentestPage = hasRolePermission(userRole, userPermissions, 'view_pentest_page');

  const goSecurity = useCallback(() => {
    if (canViewSecurity) navigate('/pentest');
  }, [canViewSecurity, navigate]);

  const goRecords = useCallback(() => {
    if (canViewRecords) navigate('/records');
  }, [canViewRecords, navigate]);

  const openApplication = useCallback(
    (appId) => {
      if (appId != null && appId !== '' && canViewSecurity) {
        navigate(`/apps/${appId}`);
        return true;
      }
      return false;
    },
    [canViewSecurity, navigate]
  );

  const openRecord = useCallback(
    (recordId) => {
      if (recordId == null || recordId === '') return false;
      if (canViewPentestPage) {
        navigate(`/pentest/record/${recordId}`);
        return true;
      }
      if (canViewRecordDetails) {
        navigate(`/records/record/${recordId}`);
        return true;
      }
      return false;
    },
    [canViewPentestPage, canViewRecordDetails, navigate]
  );

  const fetchDashboard = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true);
    setError('');
    try {
      const sourceData = await fetchDashboardSources();
      setViewModel(buildDashboardViewModel(sourceData));
    } catch (fetchError) {
      console.error('Dashboard fetch failed', fetchError);
      setError(fetchError.response?.data?.error || 'Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const intervalId = setInterval(() => fetchDashboard({ silent: true }), 60000);
    return () => clearInterval(intervalId);
  }, [fetchDashboard]);

  useEffect(() => {
    setLayout(loadLayout(username));
  }, [username]);

  const persistLayout = useCallback(
    (next) => {
      setLayout(next);
      saveLayout(username, next);
    },
    [username]
  );

  const {
    kpis,
    weekly,
    bySeverity,
    coverageGaps,
    appsAtRisk,
    testerWorkload,
    recentActivity,
    generatedAt
  } = viewModel;

  const updatedLabel = generatedAt
    ? `Updated ${new Date(generatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    : 'Waiting for data';

  const metricItems = useMemo(
    () => [
      {
        key: 'open',
        label: 'Open findings',
        value: kpis.openFindings,
        hint: `${kpis.criticalHigh} critical + high`,
        onClick: canViewSecurity ? goSecurity : undefined
      },
      {
        key: 'never',
        label: 'Never tested',
        value: kpis.neverTested,
        hint: 'No test started',
        onClick: canViewRecords ? goRecords : undefined
      },
      {
        key: 'stale',
        label: 'Stale',
        value: kpis.stale,
        hint: 'Completed over 90d ago',
        onClick: canViewRecords ? goRecords : undefined
      },
      {
        key: 'velocity',
        label: 'Closed vs opened',
        value: kpis.closedLast30d,
        hint: `${kpis.openedLast30d} opened · 30d`,
        onClick: canViewSecurity ? goSecurity : undefined
      },
      {
        key: 'unassigned',
        label: 'Unassigned',
        value: kpis.unassigned,
        hint: `${kpis.inProgress} in progress`,
        onClick: canViewSecurity ? goSecurity : undefined
      }
    ],
    [kpis, canViewSecurity, canViewRecords, goSecurity, goRecords]
  );

  const childrenById = {
    trend: <TrendWidget weekly={weekly} />,
    severity: <SeverityWidget bySeverity={bySeverity} onSelect={canViewSecurity ? goSecurity : undefined} />,
    coverage: (
      <CoverageGapsWidget
        coverageGaps={coverageGaps}
        onOpen={
          canViewSecurity || canViewRecords || canViewRecordDetails || canViewPentestPage
            ? (item) => {
                if (openApplication(item.applicationId)) return;
                if (openRecord(item.id)) return;
                goRecords();
              }
            : undefined
        }
      />
    ),
    apps: (
      <AppsAtRiskWidget
        apps={appsAtRisk}
        onOpen={canViewSecurity ? (app) => openApplication(app.id) : undefined}
      />
    ),
    workload: <TesterWorkloadWidget rows={testerWorkload} />,
    recent: (
      <RecentActivityWidget
        events={recentActivity}
        onOpen={
          canViewSecurity || canViewPentestPage || canViewRecordDetails
            ? (event) => {
                if (event.findingId && event.applicationId && canViewSecurity) {
                  navigate(`/apps/${event.applicationId}/findings/${event.findingId}`);
                  return;
                }
                if (openApplication(event.applicationId)) return;
                if (openRecord(event.recordId)) return;
              }
            : undefined
        }
      />
    )
  };

  return (
    <Page>
      <PageHeader
        title="Dashboard"
        meta={<Tag>{updatedLabel}</Tag>}
        actions={
          <>
            <Button
              variant={arranging ? 'contained' : 'outlined'}
              size="small"
              onClick={() => setArranging((value) => !value)}
            >
              {arranging ? 'Done' : 'Arrange'}
            </Button>
            {arranging ? (
              <Button
                variant="text"
                size="small"
                onClick={() =>
                  persistLayout({
                    order: [...DEFAULT_LAYOUT.order],
                    spans: { ...DEFAULT_LAYOUT.spans }
                  })
                }
              >
                Reset
              </Button>
            ) : null}
            <Button
              variant="outlined"
              size="small"
              onClick={() => fetchDashboard()}
              disabled={loading}
            >
              Refresh
            </Button>
          </>
        }
      />

      {loading ? <Progress deferred /> : null}

      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      ) : null}

      <MetricStrip items={metricItems} />

      <div style={{ marginTop: SPACE.x8 }}>
        <ArrangeGrid
          order={layout.order}
          spans={layout.spans}
          arranging={arranging}
          onReorder={(order) => persistLayout({ ...layout, order })}
          onSpanChange={(id, span) => persistLayout({ ...layout, spans: { ...layout.spans, [id]: span } })}
          childrenById={childrenById}
        />
      </div>
    </Page>
  );
};

export default Dashboard;
