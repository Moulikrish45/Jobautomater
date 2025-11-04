import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  LinearProgress,
  Fade,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Assignment as ApplicationIcon,
  CheckCircle as SuccessIcon,
  Reply as ResponseIcon,
  Schedule as TimeIcon,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from '@mui/icons-material';
import { DashboardMetrics } from '../types/api';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';

interface MetricsCardsProps {
  metrics: DashboardMetrics;
}

const MetricsCards: React.FC<MetricsCardsProps> = ({ metrics }) => {
  const theme = useTheme();
  const { isDarkMode } = useCustomTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  const cards = [
    {
      title: 'Total Applications',
      value: metrics.total_applications,
      icon: <ApplicationIcon />,
      gradient: '#667eea',
      iconBg: 'rgba(102, 126, 234, 0.2)',
      iconBorder: 'rgba(102, 126, 234, 0.3)',
      subtitle: `${metrics.applications_last_30_days} in last 30 days`,
      progress: Math.min((metrics.applications_last_30_days / 50) * 100, 100),
      trend: metrics.applications_last_30_days > 10 ? 'up' : 'down',
    },
    {
      title: 'Success Rate',
      value: `${metrics.success_rate}%`,
      icon: <SuccessIcon />,
      gradient: '#11998e',
      iconBg: 'rgba(17, 153, 142, 0.2)',
      iconBorder: 'rgba(17, 153, 142, 0.3)',
      subtitle: 'Applications completed',
      progress: metrics.success_rate,
      trend: metrics.success_rate > 50 ? 'up' : 'down',
    },
    {
      title: 'Response Rate',
      value: `${metrics.response_rate}%`,
      icon: <ResponseIcon />,
      gradient: '#3b82f6',
      iconBg: 'rgba(59, 130, 246, 0.2)',
      iconBorder: 'rgba(59, 130, 246, 0.3)',
      subtitle: 'Received responses',
      progress: metrics.response_rate,
      trend: metrics.response_rate > 30 ? 'up' : 'down',
    },
    {
      title: 'Avg Response Time',
      value: metrics.average_response_time_days 
        ? `${metrics.average_response_time_days} days`
        : 'N/A',
      icon: <TimeIcon />,
      gradient: '#f093fb',
      iconBg: 'rgba(240, 147, 251, 0.2)',
      iconBorder: 'rgba(240, 147, 251, 0.3)',
      subtitle: 'Time to hear back',
      progress: metrics.average_response_time_days 
        ? Math.max(100 - (metrics.average_response_time_days * 10), 0)
        : 0,
      trend: (metrics.average_response_time_days || 0) < 7 ? 'up' : 'down',
    },
  ];

  return (
    <Grid container spacing={3}>
      {cards.map((card, index) => (
        <Grid item xs={12} sm={6} lg={3} key={index}>
          <Fade in={true} timeout={600 + index * 200}>
            <Card
              sx={{
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                position: 'relative',
                overflow: 'hidden',
                '&:hover': {
                  transform: 'translateY(-8px)',
                  boxShadow: isDarkMode 
                    ? '0 20px 40px rgba(0, 0, 0, 0.4)'
                    : '0 20px 40px rgba(0, 0, 0, 0.15)',
                },
                '&::before': {
                  content: '""',
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  height: '4px',
                  background: card.gradient,
                },
              }}
            >
              <CardContent sx={{ p: 3 }}>
                {/* Header */}
                <Box display="flex" alignItems="center" justifyContent="space-between" mb={3}>
                  <Box
                    sx={{
                      width: 56,
                      height: 56,
                      borderRadius: '16px',
                      background: card.iconBg,
                      border: `1px solid ${card.iconBorder}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      backdropFilter: 'blur(10px)',
                    }}
                  >
                    {React.cloneElement(card.icon, { 
                      sx: { fontSize: 28, color: isDarkMode ? 'white' : '#1e293b' } 
                    })}
                  </Box>
                  <Box sx={{ textAlign: 'right' }}>
                    {card.trend === 'up' ? (
                      <TrendingUpIcon sx={{ color: '#10b981', fontSize: 20 }} />
                    ) : (
                      <TrendingDownIcon sx={{ color: '#ef4444', fontSize: 20 }} />
                    )}
                  </Box>
                </Box>

                {/* Title */}
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'text.secondary',
                    fontWeight: 500,
                    mb: 1,
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    fontSize: '0.75rem'
                  }}
                >
                  {card.title}
                </Typography>

                {/* Value */}
                <Typography 
                  variant={isMobile ? "h4" : "h3"} 
                  component="div" 
                  sx={{ 
                    color: 'text.primary',
                    fontWeight: 800,
                    mb: 2,
                    letterSpacing: '-0.02em'
                  }}
                >
                  {card.value}
                </Typography>

                {/* Progress Bar */}
                <Box sx={{ mb: 2 }}>
                  <LinearProgress
                    variant="determinate"
                    value={card.progress}
                    sx={{
                      height: 6,
                      borderRadius: 3,
                      backgroundColor: 'rgba(255, 255, 255, 0.1)',
                      '& .MuiLinearProgress-bar': {
                        borderRadius: 3,
                        background: card.gradient,
                      },
                    }}
                  />
                </Box>

                {/* Subtitle */}
                <Typography 
                  variant="body2" 
                  sx={{ 
                    color: 'rgba(255, 255, 255, 0.6)',
                    fontWeight: 400
                  }}
                >
                  {card.subtitle}
                </Typography>
              </CardContent>
            </Card>
          </Fade>
        </Grid>
      ))}

      {/* Status Breakdown */}
      <Grid item xs={12} lg={6}>
        <Fade in={true} timeout={1000}>
          <Card
            sx={{
              background: 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '20px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              '&:hover': {
                transform: 'translateY(-4px)',
                boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
              }
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Typography 
                variant="h6" 
                sx={{ 
                  color: 'white',
                  fontWeight: 600,
                  mb: 3,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1
                }}
              >
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: '#667eea',
                  }}
                />
                Application Status
              </Typography>
              <Box display="flex" flexWrap="wrap" gap={1.5}>
                {Object.entries(metrics.applications_by_status).map(([status, count]) => (
                  <Chip
                    key={status}
                    label={`${status.replace('_', ' ')}: ${count}`}
                    sx={{
                      backgroundColor: 'rgba(255, 255, 255, 0.1)',
                      color: 'white',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      backdropFilter: 'blur(10px)',
                      fontWeight: 500,
                      '&:hover': {
                        backgroundColor: 'rgba(255, 255, 255, 0.15)',
                      }
                    }}
                  />
                ))}
              </Box>
            </CardContent>
          </Card>
        </Fade>
      </Grid>

      {/* Portal Breakdown */}
      <Grid item xs={12} lg={6}>
        <Fade in={true} timeout={1200}>
          <Card
            sx={{
              background: 'rgba(255, 255, 255, 0.05)',
              backdropFilter: 'blur(20px)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '20px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
              transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              '&:hover': {
                transform: 'translateY(-4px)',
                boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)',
                border: '1px solid rgba(255, 255, 255, 0.2)',
              }
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Typography 
                variant="h6" 
                sx={{ 
                  color: 'white',
                  fontWeight: 600,
                  mb: 3,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1
                }}
              >
                <Box
                  sx={{
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: '#3b82f6',
                  }}
                />
                Applications by Portal
              </Typography>
              <Box display="flex" flexWrap="wrap" gap={1.5}>
                {Object.entries(metrics.applications_by_portal).map(([portal, count]) => (
                  <Chip
                    key={portal}
                    label={`${portal}: ${count}`}
                    sx={{
                      backgroundColor: 'rgba(59, 130, 246, 0.15)',
                      color: '#60a5fa',
                      border: '1px solid rgba(59, 130, 246, 0.3)',
                      backdropFilter: 'blur(10px)',
                      fontWeight: 500,
                      '&:hover': {
                        backgroundColor: 'rgba(59, 130, 246, 0.25)',
                      }
                    }}
                  />
                ))}
              </Box>
            </CardContent>
          </Card>
        </Fade>
      </Grid>
    </Grid>
  );
};

export default MetricsCards;