import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, Box, Grid, LinearProgress, Typography } from '@mui/material';
import DashboardHeader from './dashboard/components/DashboardHeader';
import KpiGrid from './dashboard/components/KpiGrid';
import TrendChartCard from './dashboard/components/TrendChartCard';
import RecentActivityCard from './dashboard/components/RecentActivityCard';
import TopRiskAssetsCard from './dashboard/components/TopRiskAssetsCard';
import TesterWorkloadCard from './dashboard/components/TesterWorkloadCard';
import CoverageBreakdownCard from './dashboard/components/CoverageBreakdownCard';
import { DASHBOARD_ACCENTS } from './dashboard/constants';
import { fetchDashboardSources } from './dashboard/services';
import { buildDashboardViewModel } from './dashboard/utils';

const EMPTY_VIEW_MODEL = {
  kpis: {
    totalAssets: 0,
    startedTests: 0,
    inProgressTests: 0,
    completedTests: 0,
    vulnerableAssets: 0,
    openRiskAssets: 0,
    fixedAssets: 0,
    startedLast30d: 0,
    completedLast30d: 0,
    newDetectedVulns30d: 0,
    unresolvedVulnerabilityIndicators: 0,
    averageCycleDays: 0,
    coveragePct: 0,
    fixRatePct: 0,
    ipSourceCount: 0
  },
  trends: {
    labels: [],
    testSeries: { started: [], completed: [] },
    vulnerabilitySeries: { detected: [], resolved: [] }
  },
  recentActivity: [],
  topRiskAssets: [],
  testerWorkload: [],
  generatedAt: new Date().toISOString()
};

const Dashboard = ({ userRole, userPermissions = [] }) => {
  const [viewModel, setViewModel] = useState(EMPTY_VIEW_MODEL);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isAdmin = userRole === 'admin';
  const canViewPentest =
    userPermissions.includes('view_security_dashboard') ||
    ['admin', 'manager', 'pentester'].includes(userRole);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const sourceData = await fetchDashboardSources({ canViewPentest, isAdmin });
      setViewModel(buildDashboardViewModel(sourceData));
    } catch (fetchError) {
      console.error('Dashboard fetch failed', fetchError);
      setError(fetchError.response?.data?.error || 'Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, [canViewPentest, isAdmin]);

  useEffect(() => {
    fetchDashboard();
    const intervalId = setInterval(fetchDashboard, 60000);
    return () => clearInterval(intervalId);
  }, [fetchDashboard]);

  const { kpis, trends, recentActivity, topRiskAssets, testerWorkload, generatedAt } =
    viewModel;

  const kpiItems = useMemo(
    () => [
      {
        key: 'assets',
        label: 'Total Assets',
        value: kpis.totalAssets.toLocaleString(),
        subtitle: `${kpis.ipSourceCount} source groups tracked`,
        color: DASHBOARD_ACCENTS.assets
      },
      {
        key: 'coverage',
        label: 'Testing Coverage',
        value: `${kpis.coveragePct}%`,
        subtitle: `${kpis.startedTests}/${kpis.totalAssets} assets started`,
        progress: kpis.coveragePct,
        color: DASHBOARD_ACCENTS.coverage
      },
      {
        key: 'open-risk',
        label: 'Open Risk Assets',
        value: kpis.openRiskAssets,
        subtitle: `${kpis.unresolvedVulnerabilityIndicators} unresolved indicators`,
        color: DASHBOARD_ACCENTS.risk
      },
      {
        key: 'throughput',
        label: 'Avg Test Cycle',
        value: `${kpis.averageCycleDays || 0}d`,
        subtitle: `${kpis.completedTests} completed, ${kpis.inProgressTests} in progress`,
        color: DASHBOARD_ACCENTS.throughput
      },
      {
        key: 'started-30d',
        label: 'Started (30d)',
        value: kpis.startedLast30d,
        subtitle: 'Recently initiated tests',
        color: DASHBOARD_ACCENTS.started
      },
      {
        key: 'completed-30d',
        label: 'Completed (30d)',
        value: kpis.completedLast30d,
        subtitle: `Fix rate ${kpis.fixRatePct}%`,
        color: DASHBOARD_ACCENTS.completed
      },
      {
        key: 'new-vulns-30d',
        label: 'New Vuln Findings (30d)',
        value: kpis.newDetectedVulns30d,
        subtitle: `${kpis.vulnerableAssets} vulnerable assets`,
        color: DASHBOARD_ACCENTS.detected
      },
      {
        key: 'fixed-assets',
        label: 'Fixed Assets',
        value: kpis.fixedAssets,
        subtitle: 'Assets marked remediated',
        color: DASHBOARD_ACCENTS.resolved
      }
    ],
    [kpis]
  );

  if (loading && kpis.totalAssets === 0) {
    return (
      <Box sx={{ p: 3, minHeight: '100vh', backgroundColor: 'background.default' }}>
        <Typography variant="h6" color="text.secondary" sx={{ mb: 1.5 }}>
          Loading dashboard...
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3, minHeight: '100vh', backgroundColor: 'background.default' }}>
      <DashboardHeader generatedAt={generatedAt} onRefresh={fetchDashboard} loading={loading} />

      {loading && <LinearProgress sx={{ mb: 2 }} />}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <KpiGrid items={kpiItems} />

      <Grid container spacing={2} mb={2}>
        <Grid item xs={12} lg={6}>
          <TrendChartCard
            title="Test Throughput Trend"
            subtitle="Started vs completed tests over the last six months."
            labels={trends.labels}
            series={[
              {
                key: 'started',
                label: 'Started',
                color: DASHBOARD_ACCENTS.started,
                data: trends.testSeries.started
              },
              {
                key: 'completed',
                label: 'Completed',
                color: DASHBOARD_ACCENTS.completed,
                data: trends.testSeries.completed
              }
            ]}
          />
        </Grid>
        <Grid item xs={12} lg={6}>
          <TrendChartCard
            title="Vulnerability Trend"
            subtitle="Detected and resolved findings over the last six months."
            labels={trends.labels}
            series={[
              {
                key: 'detected',
                label: 'Detected',
                color: DASHBOARD_ACCENTS.detected,
                data: trends.vulnerabilitySeries.detected
              },
              {
                key: 'resolved',
                label: 'Resolved',
                color: DASHBOARD_ACCENTS.resolved,
                data: trends.vulnerabilitySeries.resolved
              }
            ]}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2} mb={2}>
        <Grid item xs={12} lg={6}>
          <RecentActivityCard events={recentActivity} />
        </Grid>
        <Grid item xs={12} lg={6}>
          <TopRiskAssetsCard assets={topRiskAssets} />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} lg={7}>
          <TesterWorkloadCard rows={testerWorkload} />
        </Grid>
        <Grid item xs={12} lg={5}>
          <CoverageBreakdownCard kpis={kpis} />
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;
