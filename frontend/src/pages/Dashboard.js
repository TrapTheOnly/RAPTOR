import axios from 'axios';
import { useState, useEffect } from 'react';
import { 
  Box, 
  Grid, 
  Card, 
  CardContent, 
  Typography, 
  Paper,
  LinearProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  useTheme
} from '@mui/material';
import {
  TrendingUp,
  Security,
  Warning,
  CheckCircle,
  Computer,
  Assessment,
  Timeline,
  Refresh
} from '@mui/icons-material';

const Dashboard = ({ userRole, darkMode = false }) => {
  const [stats, setStats] = useState({
    totalRecords: 0,
    vulnerableRecords: 0,
    testedRecords: 0,
    recentChanges: 0,
    testsThisMonth: 0,
    testsThisYear: 0,
    ipSources: 0,
    testsInProgress: 0,
    completedTests: 0
  });
  
  const [records, setRecords] = useState([]);
  const [pentestData, setPentestData] = useState([]);
  const [recentActivity, setRecentActivity] = useState([]);
  const [loading, setLoading] = useState(true);
  const theme = useTheme();

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    try {
      // Fetch all data sources
      const [recordsResponse, pentestResponse, usersResponse, sourcesResponse] = await Promise.all([
        axios.get('/api/records'),
        userRole === 'admin' || userRole === 'pentester' ? axios.get('/pentest/records') : Promise.resolve({ data: [] }),
        userRole === 'admin' ? axios.get('/existing-users') : Promise.resolve({ data: { users: [] } }),
        userRole === 'admin' ? axios.get('/ip-sources') : Promise.resolve({ data: { ip_sources: [] } })
      ]);

      const recordsData = recordsResponse.data;
      const pentestDataRes = pentestResponse.data || [];
      const usersData = usersResponse.data?.users || [];
      const sourcesData = sourcesResponse.data?.ip_sources || [];

      setRecords(recordsData);
      setPentestData(pentestDataRes);

      // Calculate statistics
      const totalRecords = recordsData.length;
      const recentChanges = recordsData.filter(r => r.status === 'updated' || r.status === 'missing').length;
      
      // Pentest statistics
      const vulnerableRecords = pentestDataRes.filter(p => p.vulnerable === 1).length;
      const testedRecords = pentestDataRes.filter(p => p.status === 'Completed').length;
      const testsInProgress = pentestDataRes.filter(p => p.status === 'In Progress').length;
      
      // Calculate tests completed this month
      const now = new Date();
      const firstDayOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
      const lastDayOfMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0);

      const firstDayOfYear = new Date(now.getFullYear(), 0, 1)
      const lastDayOfYear = new Date(now.getFullYear(), 12, 31)
      
      const testsThisMonth = pentestDataRes.filter(p => {
        if (p.status === 'Completed' && p.test_end_date) {
          const testEndDate = new Date(p.test_end_date);
          return testEndDate >= firstDayOfMonth && testEndDate <= lastDayOfMonth;
        }
        return false;
      }).length;

      const testsThisYear = pentestDataRes.filter(p => {
        if (p.status === 'Completed' && p.test_end_date) {
          const testEndDate = new Date(p.test_end_date);
          return testEndDate >= firstDayOfYear && testEndDate <= lastDayOfYear;
        }
        return false;
      }).length;
      
      const uniqueSources = [...new Set(sourcesData.map(s => s.source_name))].length;

      setStats({
        totalRecords,
        vulnerableRecords,
        testedRecords,
        recentChanges,
        testsThisMonth,
        testsThisYear,
        ipSources: uniqueSources,
        testsInProgress,
        completedTests: testedRecords
      });

      // Generate recent activity
      const activity = [];
      recordsData.slice(0, 5).forEach(record => {
        if (record.status === 'updated') {
          activity.push({
            type: 'record_updated',
            title: `Asset Record Updated`,
            subtitle: record.name,
            time: record.last_modification_date,
            icon: TrendingUp,
            color: '#4CAF50'
          });
        } else if (record.status === 'missing') {
          activity.push({
            type: 'record_missing',
            title: `Asset Missing from Scope`,
            subtitle: record.name,
            time: record.last_modification_date,
            icon: Warning,
            color: '#FF9800'
          });
        }
      });

      pentestDataRes.slice(0, 3).forEach(pentest => {
        if (pentest.status === 'Completed') {
          activity.push({
            type: 'pentest_completed',
            title: `Security Test Completed`,
            subtitle: pentest.name,
            time: pentest.test_end_date,
            icon: Security,
            color: pentest.vulnerable ? '#F44336' : '#4CAF50'
          });
        }
      });

      setRecentActivity(activity.slice(0, 6));

    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const MetricCard = ({ title, value, subtitle, icon: Icon, progress, color = '#ffffff' }) => (
    <Card sx={{ height: '100%' }}>
      <CardContent sx={{ p: 3 }}>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              {title}
            </Typography>
            <Typography variant="h4" component="div" sx={{ fontWeight: 300, mb: 1 }}>
              {value}
            </Typography>
            {subtitle && (
              <Typography variant="body2" color="text.secondary">
                {subtitle}
              </Typography>
            )}
          </Box>
          <Icon sx={{ color, opacity: 0.7 }} />
        </Box>
        {progress !== undefined && (
          <Box mt={2}>
            <LinearProgress 
              variant="determinate" 
              value={progress} 
              sx={{
                '& .MuiLinearProgress-bar': {
                  backgroundColor: color,
                },
              }}
            />
          </Box>
        )}
      </CardContent>
    </Card>
  );

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
          <Typography variant="h6" color="text.secondary">Loading dashboard...</Typography>
        </Box>
    );
  }

  return (
      <Box sx={{ p: 3, minHeight: '100vh', backgroundColor: 'background.default' }}>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={4}>
          <Box>
            <Typography variant="h4" gutterBottom>
              Security Overview
            </Typography>
            <Typography variant="body2" color="text.secondary">
              DNS monitoring and security assessment dashboard
            </Typography>
          </Box>
          <IconButton onClick={fetchDashboardData} sx={{ color: 'text.secondary' }}>
            <Refresh />
          </IconButton>
        </Box>

        {/* Key Metrics */}
        <Grid container spacing={3} mb={4}>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Total Records"
              value={stats.totalRecords.toLocaleString()}
              subtitle={`${stats.recentChanges} recent changes`}
              icon={Computer}
              color="#4CAF50"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Vulnerable Systems"
              value={stats.vulnerableRecords}
              subtitle={`${stats.testedRecords} tested`}
              icon={Warning}
              progress={stats.totalRecords > 0 ? (stats.vulnerableRecords / stats.totalRecords) * 100 : 0}
              color="#F44336"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
              title="Security Tests"
              value={stats.completedTests}
              subtitle={`${stats.testsInProgress} in progress`}
              icon={Security}
              progress={stats.totalRecords > 0 ? (stats.completedTests / stats.totalRecords) * 100 : 0}
              color="#2196F3"
            />
          </Grid>
          <Grid item xs={12} sm={6} md={3}>
            <MetricCard
            title="Tests This Month"
            value={stats.testsThisMonth}
            subtitle={`${stats.testsThisYear} tests this year`}
            icon={Timeline}
              color="#9C27B0"
            />
          </Grid>
        </Grid>

        {/* Content Grid */}
        <Grid container spacing={3}>
          {/* Recent Activity */}
          <Grid item xs={12} md={6}>
            <Card sx={{ height: 400 }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  Recent Activity
                </Typography>
                <Box sx={{ mt: 2 }}>
                  {recentActivity.length > 0 ? (
                    recentActivity.map((activity, index) => (
                      <Box key={index} display="flex" alignItems="center" py={1.5}>
                        <Box
                          sx={{
                            width: 32,
                            height: 32,
                            borderRadius: '50%',
                            backgroundColor: activity.color + '20',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            mr: 2,
                          }}
                        >
                          <activity.icon sx={{ fontSize: 16, color: activity.color }} />
                        </Box>
                        <Box flex={1}>
                          <Typography variant="body2" sx={{ fontWeight: 500 }}>
                            {activity.title}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {activity.subtitle}
                          </Typography>
                        </Box>
                        <Typography variant="caption" color="text.secondary">
                          {formatDate(activity.time)}
                        </Typography>
                      </Box>
                    ))
                  ) : (
                    <Typography variant="body2" color="text.secondary" textAlign="center" py={4}>
                      No recent activity
                    </Typography>
                  )}
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* System Status */}
          <Grid item xs={12} md={6}>
            <Card sx={{ height: 400 }}>
              <CardContent sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  System Status
                </Typography>
                <Box sx={{ mt: 3 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" py={2}>
                    <Box display="flex" alignItems="center">
                      <CheckCircle sx={{ color: '#4CAF50', mr: 2 }} />
                      <Typography variant="body2">DNS Monitoring</Typography>
                    </Box>
                    <Chip label="Active" size="small" sx={{ backgroundColor: '#4CAF50', color: 'white' }} />
                  </Box>
                  
                  <Box display="flex" justifyContent="space-between" alignItems="center" py={2}>
                    <Box display="flex" alignItems="center">
                      <Security sx={{ color: '#2196F3', mr: 2 }} />
                    <Typography variant="body2">Live Security Testing</Typography>
                    </Box>
                    <Chip 
                    label={stats.testsInProgress > 0 ? "Active" : "Idle"} 
                      size="small" 
                      sx={{ 
                      backgroundColor: stats.testsInProgress > 0 ? '#4CAF50' : '#666666', 
                        color: 'white' 
                      }} 
                    />
                  </Box>
                  
                  <Box display="flex" justifyContent="space-between" alignItems="center" py={2}>
                    <Box display="flex" alignItems="center">
                      <Assessment sx={{ color: '#9C27B0', mr: 2 }} />
                      <Typography variant="body2">Data Collection</Typography>
                    </Box>
                    <Chip label="Active" size="small" sx={{ backgroundColor: '#4CAF50', color: 'white' }} />
                  </Box>

                  {/* Quick Stats */}
                  <Box mt={4} p={2} sx={{ backgroundColor: 'background.default', borderRadius: 1 }}>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">
                          Last Update
                        </Typography>
                        <Typography variant="body2">
                          {formatDate(new Date().toISOString())}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography variant="caption" color="text.secondary">
                        Security Test Coverage
                        </Typography>
                        <Typography variant="body2">
                          {stats.totalRecords > 0 ? Math.round((stats.testedRecords / stats.totalRecords) * 100) : 0}%
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
  );
};

export default Dashboard;