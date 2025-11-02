import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  Box,
} from '@mui/material';
import {
  Work as WorkIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Schedule as PendingIcon,
} from '@mui/icons-material';
import { format, parseISO } from 'date-fns';
import { ActivityItem, ApplicationStatus } from '../types/api';

interface RecentActivityProps {
  activities: ActivityItem[];
}

const RecentActivity: React.FC<RecentActivityProps> = ({ activities }) => {
  const getStatusIcon = (status: ApplicationStatus) => {
    switch (status) {
      case ApplicationStatus.COMPLETED:
        return <SuccessIcon color="success" />;
      case ApplicationStatus.FAILED:
        return <ErrorIcon color="error" />;
      case ApplicationStatus.IN_PROGRESS:
        return <PendingIcon color="warning" />;
      default:
        return <WorkIcon color="primary" />;
    }
  };

  const getStatusColor = (status: ApplicationStatus) => {
    switch (status) {
      case ApplicationStatus.COMPLETED:
        return 'success';
      case ApplicationStatus.FAILED:
        return 'error';
      case ApplicationStatus.IN_PROGRESS:
        return 'warning';
      default:
        return 'default';
    }
  };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Recent Activity
        </Typography>
        {activities.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No recent activity
          </Typography>
        ) : (
          <List>
            {activities.map((activity, index) => (
              <ListItem key={index} divider={index < activities.length - 1}>
                <ListItemIcon>
                  {getStatusIcon(activity.status)}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box display="flex" alignItems="center" gap={1}>
                      <Typography variant="subtitle2">
                        {activity.job_title}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        at {activity.company}
                      </Typography>
                    </Box>
                  }
                  secondary={
                    <Box display="flex" alignItems="center" gap={1} mt={0.5}>
                      <Chip
                        label={activity.status.replace('_', ' ')}
                        size="small"
                        color={getStatusColor(activity.status) as any}
                        variant="outlined"
                      />
                      {activity.outcome && (
                        <Chip
                          label={activity.outcome.replace('_', ' ')}
                          size="small"
                          variant="outlined"
                        />
                      )}
                      <Typography variant="caption" color="text.secondary">
                        {format(parseISO(activity.created_at), 'MMM dd, yyyy')}
                      </Typography>
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default RecentActivity;