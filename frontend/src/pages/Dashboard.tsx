import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
  Container,
  Fade,
  useTheme,
  Chip,
  LinearProgress,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  Divider,
} from '@mui/material';
import {
  TrendingUp as TrendingUpIcon,
  Analytics as AnalyticsIcon,
  Work as WorkIcon,
  CheckCircle as CheckCircleIcon,
  Schedule as ScheduleIcon,
  Error as ErrorIcon,
  Business as BusinessIcon,
  Person as PersonIcon,
  Email as EmailIcon,
  Phone as PhoneIcon,
} from '@mui/icons-material';
import MetricsCards from '../components/MetricsCards';
import { useAuth } from '../contexts/AuthContext';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import { useNotifications } from '../contexts/NotificationContext';
import { DashboardMetrics, ApplicationStatus, ApplicationOutcome, JobPortal } from '../types/api';

// Mock data interfaces for local use
interface RecentActivity {
  id: string;
  type: 'application_submitted' | 'response_received' | 'interview_scheduled' | 'application_rejected';
  title: string;
  company: string;
  timestamp: string;
  status: 'success' | 'info' | 'warning' | 'error';
}

const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();
  const theme = useTheme();
  const { isDarkMode } = useCustomTheme();
  const { isWebSocketConnected, addNotification } = useNotifications();

  // Mock data generator
  const generateMockData = useCallback((): DashboardMetrics => {
    const now = new Date();
    const activities: RecentActivity[] = [
      {
        id: '1',
        type: 'application_submitted',
        title: 'Senior Frontend Developer',
        company: 'TechCorp Inc.',
        timestamp: new Date(now.getTime() - 2 * 60 * 60 * 1000).toISOString(),
        status: 'info'
      },
      {
        id: '2',
        type: 'response_received',
        title: 'Full Stack Engineer',
        company: 'StartupXYZ',
        timestamp: new Date(now.getTime() - 4 * 60 * 60 * 1000).toISOString(),
        status: 'success'
      },
      {
        id: '3',
        type: 'interview_scheduled',
        title: 'React Developer',
        company: 'WebSolutions Ltd',
        timestamp: new Date(now.getTime() - 6 * 60 * 60 * 1000).toISOString(),
        status: 'success'
      },
      {
        id: '4',
        type: 'application_rejected',
        title: 'Software Engineer',
        company: 'BigTech Corp',
        timestamp: new Date(now.getTime() - 8 * 60 * 60 * 1000).toISOString(),
        status: 'error'
      },
      {
        id: '5',
        type: 'application_submitted',
        title: 'DevOps Engineer',
        company: 'CloudFirst',
        timestamp: new Date(now.getTime() - 12 * 60 * 60 * 1000).toISOString(),
        status: 'info'
      }
    ];

    return {
      total_applications: 47,
      applications_last_30_days: 12,
      success_rate: 68,
      response_rate: 45,
      average_response_time_days: 5,
      interviews_scheduled: 8,
      offers_received: 3,
      applications_by_status: {
        [ApplicationStatus.PENDING]: 8,
        [ApplicationStatus.IN_PROGRESS]: 12,
        [ApplicationStatus.COMPLETED]: 22,
        [ApplicationStatus.FAILED]: 5,
        [ApplicationStatus.CANCELLED]: 0
      },
      applications_by_outcome: {
        [ApplicationOutcome.APPLIED]: 22,
        [ApplicationOutcome.VIEWED]: 15,
        [ApplicationOutcome.REJECTED]: 15,
        [ApplicationOutcome.INTERVIEW_SCHEDULED]: 8,
        [ApplicationOutcome.INTERVIEW_COMPLETED]: 5,
        [ApplicationOutcome.OFFER_RECEIVED]: 3,
        [ApplicationOutcome.OFFER_ACCEPTED]: 1,
        [ApplicationOutcome.OFFER_DECLINED]: 0
      },
      applications_by_portal: {
        [JobPortal.LINKEDIN]: 18,
        [JobPortal.INDEED]: 12,
        [JobPortal.NAUKRI]: 17
      },
      monthly_trends: [
        { month: '2024-01', applications: 15, responses: 8, interviews: 3, offers: 1 },
        { month: '2024-02', applications: 18, responses: 10, interviews: 4, offers: 2 },
        { month: '2024-03', applications: 14, responses: 7, interviews: 1, offers: 0 }
      ],
      recent_activity: activities.map(activity => ({
        job_title: activity.title,
        company: activity.company,
        status: ApplicationStatus.COMPLETED,
        outcome: ApplicationOutcome.APPLIED,
        created_at: activity.timestamp,
        applied_at: activity.timestamp
      })),
      top_companies: [
        { name: 'TechCorp Inc.', applications: 3, avg_match_score: 85 },
        { name: 'StartupXYZ', applications: 2, avg_match_score: 92 },
        { name: 'WebSolutions Ltd', applications: 4, avg_match_score: 78 },
        { name: 'BigTech Corp', applications: 5, avg_match_score: 65 },
        { name: 'CloudFirst', applications: 2, avg_match_score: 88 }
      ]
    };
  }, []);

  // Simulate real-time updates
  useEffect(() => {
    const loadDashboardData = () => {
      setLoading(true);
      setError(null);

      // Simulate API call delay
      setTimeout(() => {
        try {
          const mockData = generateMockData();
          setMetrics(mockData);
          setLoading(false);
        } catch (err) {
          setError('Failed to load dashboard data. Please try again.');
          setLoading(false);
        }
      }, 1000);
    };

    loadDashboardData();

    // Simulate periodic updates every 30 seconds
    const interval = setInterval(() => {
      if (isWebSocketConnected) {
        // Simulate receiving real-time updates
        const updateTypes = ['new_application', 'status_update', 'response_received'];
        const randomUpdate = updateTypes[Math.floor(Math.random() * updateTypes.length)];
        
        if (Math.random() > 0.7) { // 30% chance of update
          setMetrics(prev => {
            if (!prev) return prev;
            
            const updated = { ...prev };
            
            switch (randomUpdate) {
              case 'new_application':
                updated.total_applications += 1;
                updated.applications_last_30_days += 1;
                addNotification({
                  type: 'info',
                  message: 'New application submitted automatically',
                  autoHide: true,
                  duration: 3000,
                });
                break;
              case 'status_update':
                addNotification({
                  type: 'success',
                  message: 'Application status updated: Under Review',
                  autoHide: true,
                  duration: 3000,
                });
                break;
              case 'response_received':
                updated.response_rate = Math.min(updated.response_rate + 1, 100);
                addNotification({
                  type: 'success',
                  message: 'New response received from TechCorp Inc.',
                  autoHide: true,
                  duration: 4000,
                });
                break;
            }
            
            return updated;
          });
        }
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [generateMockData, isWebSocketConnected, addNotification]);

  if (loading) {
    return (
      <Container maxWidth="xl" sx={{ py: 2, px: 2 }}>
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
          <Box textAlign="center">
            <CircularProgress 
              size={60} 
              thickness={4}
              sx={{ 
                color: 'primary.main',
                mb: 2
              }} 
            />
            <Typography variant="h6" sx={{ color: 'text.secondary' }}>
              Loading your dashboard...
            </Typography>
          </Box>
        </Box>
      </Container>
    );
  }

  if (error) {
    return (
      <Container maxWidth="xl" sx={{ py: 2, px: 2 }}>
        <Alert 
          severity="error" 
          sx={{ 
            backgroundColor: isDarkMode 
              ? 'rgba(244, 67, 54, 0.1)'
              : 'rgba(244, 67, 54, 0.05)',
            border: `1px solid rgba(244, 67, 54, ${isDarkMode ? '0.3' : '0.2'})`,
            borderRadius: '16px',
            backdropFilter: 'blur(10px)',
            color: 'text.primary',
            '& .MuiAlert-icon': { color: '#f44336' }
          }}
        >
          {error}
        </Alert>
      </Container>
    );
  }

  if (!metrics) {
    return (
      <Container maxWidth="xl" sx={{ py: 2, px: 2 }}>
        <Alert 
          severity="info"
          sx={{ 
            backgroundColor: isDarkMode 
              ? 'rgba(33, 150, 243, 0.1)'
              : 'rgba(33, 150, 243, 0.05)',
            border: `1px solid rgba(33, 150, 243, ${isDarkMode ? '0.3' : '0.2'})`,
            borderRadius: '16px',
            backdropFilter: 'blur(10px)',
            color: 'text.primary',
            '& .MuiAlert-icon': { color: '#2196f3' }
          }}
        >
          No dashboard data available.
        </Alert>
      </Container>
    );
  }



  const formatTimeAgo = (timestamp: string) => {
    const now = new Date();
    const time = new Date(timestamp);
    const diffInHours = Math.floor((now.getTime() - time.getTime()) / (1000 * 60 * 60));
    
    if (diffInHours < 1) return 'Just now';
    if (diffInHours < 24) return `${diffInHours}h ago`;
    const diffInDays = Math.floor(diffInHours / 24);
    return `${diffInDays}d ago`;
  };

  return (
    <Container maxWidth="xl" sx={{ py: 2, px: 2 }}>
      <Fade in={true} timeout={800}>
        <Box>
          {/* Welcome Section */}
          <Box sx={{ mb: 4 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Box>
                <Typography 
                  variant="h4" 
                  sx={{ 
                    fontWeight: 700,
                    color: 'text.primary',
                    mb: 0.5
                  }}
                >
                  Welcome back, {user?.first_name || 'User'}!
                </Typography>
                <Typography 
                  variant="body1" 
                  sx={{ 
                    color: 'text.secondary',
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1
                  }}
                >
                  <AnalyticsIcon sx={{ fontSize: 20 }} />
                  Real-time insights into your job application journey
                </Typography>
              </Box>
              <Chip
                icon={isWebSocketConnected ? <CheckCircleIcon /> : <ErrorIcon />}
                label={isWebSocketConnected ? 'Live Updates' : 'Offline Mode'}
                color={isWebSocketConnected ? 'success' : 'default'}
                variant="outlined"
                sx={{ 
                  fontWeight: 500,
                  '& .MuiChip-icon': { 
                    color: isWebSocketConnected ? '#10b981' : '#6b7280' 
                  }
                }}
              />
            </Box>
          </Box>

          <Grid container spacing={3}>
            {/* Metrics Cards */}
            <Grid item xs={12}>
              <MetricsCards metrics={metrics} />
            </Grid>

            {/* Quick Stats */}
            <Grid item xs={12} md={8}>
              <Card
                sx={{
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: theme.palette.mode === 'dark' 
                      ? '0 12px 40px rgba(0, 0, 0, 0.4)'
                      : '0 12px 40px rgba(0, 0, 0, 0.15)',
                  }
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                    <Box
                      sx={{
                        width: 48,
                        height: 48,
                        borderRadius: '12px',
                        background: 'rgba(139, 92, 246, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mr: 2,
                        border: '1px solid rgba(139, 92, 246, 0.3)',
                      }}
                    >
                      <TrendingUpIcon sx={{ color: '#8b5cf6', fontSize: 24 }} />
                    </Box>
                    <Box>
                      <Typography 
                        variant="h6" 
                        sx={{ 
                          color: 'text.primary',
                          fontWeight: 600,
                          mb: 0.5
                        }}
                      >
                        Application Progress
                      </Typography>
                      <Typography 
                        variant="body2" 
                        sx={{ color: 'text.secondary' }}
                      >
                        Your current application pipeline
                      </Typography>
                    </Box>
                  </Box>

                  {/* Progress Bars */}
                  <Grid container spacing={3}>
                    <Grid item xs={12} sm={6}>
                      <Box sx={{ mb: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Response Rate
                          </Typography>
                          <Typography variant="body2" color="text.primary" fontWeight={600}>
                            {metrics?.response_rate}%
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={metrics?.response_rate || 0}
                          sx={{
                            height: 8,
                            borderRadius: 4,
                            backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                            '& .MuiLinearProgress-bar': {
                              borderRadius: 4,
                              background: '#10b981',
                            },
                          }}
                        />
                      </Box>
                    </Grid>
                    <Grid item xs={12} sm={6}>
                      <Box sx={{ mb: 2 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" color="text.secondary">
                            Success Rate
                          </Typography>
                          <Typography variant="body2" color="text.primary" fontWeight={600}>
                            {metrics?.success_rate}%
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={metrics?.success_rate || 0}
                          sx={{
                            height: 8,
                            borderRadius: 4,
                            backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)',
                            '& .MuiLinearProgress-bar': {
                              borderRadius: 4,
                              background: '#3b82f6',
                            },
                          }}
                        />
                      </Box>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Grid>

            {/* Top Companies */}
            <Grid item xs={12} md={4}>
              <Card
                sx={{
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: theme.palette.mode === 'dark' 
                      ? '0 12px 40px rgba(0, 0, 0, 0.4)'
                      : '0 12px 40px rgba(0, 0, 0, 0.15)',
                  }
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                    <Box
                      sx={{
                        width: 48,
                        height: 48,
                        borderRadius: '12px',
                        background: 'rgba(59, 130, 246, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mr: 2,
                        border: '1px solid rgba(59, 130, 246, 0.3)',
                      }}
                    >
                      <BusinessIcon sx={{ color: '#3b82f6', fontSize: 24 }} />
                    </Box>
                    <Box>
                      <Typography 
                        variant="h6" 
                        sx={{ 
                          color: 'text.primary',
                          fontWeight: 600,
                          mb: 0.5
                        }}
                      >
                        Top Companies
                      </Typography>
                      <Typography 
                        variant="body2" 
                        sx={{ color: 'text.secondary' }}
                      >
                        Most applied companies
                      </Typography>
                    </Box>
                  </Box>

                  <List sx={{ p: 0 }}>
                    {metrics?.top_companies.slice(0, 5).map((company, index) => (
                      <ListItem key={company.name} sx={{ px: 0, py: 1 }}>
                        <ListItemAvatar>
                          <Avatar sx={{ bgcolor: 'primary.main', width: 32, height: 32 }}>
                            {company.name.charAt(0)}
                          </Avatar>
                        </ListItemAvatar>
                        <ListItemText
                          primary={company.name}
                          secondary={`${company.applications} applications`}
                          primaryTypographyProps={{ fontSize: '0.875rem', fontWeight: 500 }}
                          secondaryTypographyProps={{ fontSize: '0.75rem' }}
                        />
                        <Chip
                          label={`${company.avg_match_score}%`}
                          size="small"
                          color={company.avg_match_score > 70 ? 'success' : 'default'}
                          sx={{ fontSize: '0.75rem' }}
                        />
                      </ListItem>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>

            {/* Recent Activity */}
            <Grid item xs={12}>
              <Card
                sx={{
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  '&:hover': {
                    transform: 'translateY(-4px)',
                    boxShadow: theme.palette.mode === 'dark' 
                      ? '0 12px 40px rgba(0, 0, 0, 0.4)'
                      : '0 12px 40px rgba(0, 0, 0, 0.15)',
                  }
                }}
              >
                <CardContent sx={{ p: 3 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                    <Box
                      sx={{
                        width: 48,
                        height: 48,
                        borderRadius: '12px',
                        background: 'rgba(16, 185, 129, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mr: 2,
                        border: '1px solid rgba(16, 185, 129, 0.3)',
                      }}
                    >
                      <PersonIcon sx={{ color: '#10b981', fontSize: 24 }} />
                    </Box>
                    <Box>
                      <Typography 
                        variant="h6" 
                        sx={{ 
                          color: 'text.primary',
                          fontWeight: 600,
                          mb: 0.5
                        }}
                      >
                        Recent Activity
                      </Typography>
                      <Typography 
                        variant="body2" 
                        sx={{ color: 'text.secondary' }}
                      >
                        Latest application updates
                      </Typography>
                    </Box>
                  </Box>

                  <List sx={{ p: 0 }}>
                    {metrics?.recent_activity.map((activity, index) => (
                      <React.Fragment key={`${activity.job_title}-${index}`}>
                        <ListItem sx={{ px: 0, py: 2 }}>
                          <ListItemAvatar>
                            <Avatar sx={{ bgcolor: 'transparent', width: 40, height: 40 }}>
                              <WorkIcon sx={{ color: '#3b82f6' }} />
                            </Avatar>
                          </ListItemAvatar>
                          <ListItemText
                            primary={`${activity.job_title} at ${activity.company}`}
                            secondary={formatTimeAgo(activity.created_at)}
                            primaryTypographyProps={{ fontSize: '0.875rem', fontWeight: 500 }}
                            secondaryTypographyProps={{ fontSize: '0.75rem' }}
                          />
                          <Chip
                            label={activity.status}
                            size="small"
                            color={activity.status === ApplicationStatus.COMPLETED ? 'success' : 'default'}
                            variant="outlined"
                            sx={{ fontSize: '0.75rem', textTransform: 'capitalize' }}
                          />
                        </ListItem>
                        {index < metrics.recent_activity.length - 1 && <Divider />}
                      </React.Fragment>
                    ))}
                  </List>
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      </Fade>
    </Container>
  );
};

export default Dashboard;