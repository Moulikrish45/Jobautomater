import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
} from '@mui/material';
import {
  Assignment as ApplicationIcon,
  CheckCircle as SuccessIcon,
  Reply as ResponseIcon,
  Schedule as TimeIcon,
} from '@mui/icons-material';
import { DashboardMetrics } from '../types/api';

interface MetricsCardsProps {
  metrics: DashboardMetrics;
}

const MetricsCards: React.FC<MetricsCardsProps> = ({ metrics }) => {
  const cards = [
    {
      title: 'Total Applications',
      value: metrics.total_applications,
      icon: <ApplicationIcon color="primary" />,
      color: 'primary.main',
      subtitle: `${metrics.applications_last_30_days} in last 30 days`,
    },
    {
      title: 'Success Rate',
      value: `${metrics.success_rate}%`,
      icon: <SuccessIcon color="success" />,
      color: 'success.main',
      subtitle: 'Applications completed',
    },
    {
      title: 'Response Rate',
      value: `${metrics.response_rate}%`,
      icon: <ResponseIcon color="info" />,
      color: 'info.main',
      subtitle: 'Received responses',
    },
    {
      title: 'Avg Response Time',
      value: metrics.average_response_time_days 
        ? `${metrics.average_response_time_days} days`
        : 'N/A',
      icon: <TimeIcon color="warning" />,
      color: 'warning.main',
      subtitle: 'Time to hear back',
    },
  ];

  return (
    <Grid container spacing={3}>
      {cards.map((card, index) => (
        <Grid item xs={12} sm={6} md={3} key={index}>
          <Card>
            <CardContent>
              <Box display="flex" alignItems="center" mb={2}>
                {card.icon}
                <Typography variant="h6" component="div" ml={1}>
                  {card.title}
                </Typography>
              </Box>
              <Typography variant="h4" component="div" color={card.color}>
                {card.value}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {card.subtitle}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}

      {/* Status Breakdown */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Application Status
            </Typography>
            <Box display="flex" flexWrap="wrap" gap={1}>
              {Object.entries(metrics.applications_by_status).map(([status, count]) => (
                <Chip
                  key={status}
                  label={`${status}: ${count}`}
                  variant="outlined"
                  size="small"
                />
              ))}
            </Box>
          </CardContent>
        </Card>
      </Grid>

      {/* Portal Breakdown */}
      <Grid item xs={12} md={6}>
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Applications by Portal
            </Typography>
            <Box display="flex" flexWrap="wrap" gap={1}>
              {Object.entries(metrics.applications_by_portal).map(([portal, count]) => (
                <Chip
                  key={portal}
                  label={`${portal}: ${count}`}
                  variant="outlined"
                  size="small"
                  color="primary"
                />
              ))}
            </Box>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );
};

export default MetricsCards;