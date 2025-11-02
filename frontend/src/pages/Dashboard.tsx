import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
} from '@mui/material';
import MetricsCards from '../components/MetricsCards';
import ApplicationChart from '../components/ApplicationChart';
import RecentActivity from '../components/RecentActivity';
import TopCompanies from '../components/TopCompanies';
import { DashboardMetrics, ApplicationTrend } from '../types/api';
import DashboardAPI from '../services/api';

const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [trends, setTrends] = useState<ApplicationTrend[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // TODO: Get user ID from authentication context
  const userId = 'user123'; // Placeholder

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        setError(null);

        const [metricsData, trendsData] = await Promise.all([
          DashboardAPI.getDashboardMetrics(userId, 30),
          DashboardAPI.getApplicationTrends(userId, 30),
        ]);

        setMetrics(metricsData);
        setTrends(trendsData);
      } catch (err) {
        console.error('Failed to fetch dashboard data:', err);
        setError('Failed to load dashboard data. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, [userId]);

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box p={2}>
        <Alert severity="error">{error}</Alert>
      </Box>
    );
  }

  if (!metrics) {
    return (
      <Box p={2}>
        <Alert severity="info">No dashboard data available.</Alert>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Dashboard
      </Typography>

      <Grid container spacing={3}>
        {/* Metrics Cards */}
        <Grid item xs={12}>
          <MetricsCards metrics={metrics} />
        </Grid>

        {/* Application Trends Chart */}
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Application Trends (Last 30 Days)
              </Typography>
              <ApplicationChart data={trends} />
            </CardContent>
          </Card>
        </Grid>

        {/* Top Companies */}
        <Grid item xs={12} md={4}>
          <TopCompanies companies={metrics.top_companies} />
        </Grid>

        {/* Recent Activity */}
        <Grid item xs={12}>
          <RecentActivity activities={metrics.recent_activity} />
        </Grid>
      </Grid>
    </Box>
  );
};

export default Dashboard;