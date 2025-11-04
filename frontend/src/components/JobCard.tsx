import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Link,
  Divider,
} from '@mui/material';
import {
  LocationOn as LocationIcon,
  Business as BusinessIcon,
  TrendingUp as TrendingUpIcon,
  OpenInNew as OpenInNewIcon,
} from '@mui/icons-material';
import AutoApplyButton from './AutoApplyButton';

export interface JobCardProps {
  job: {
    id: string;
    title: string;
    company: string;
    location: string;
    description: string;
    url: string;
    portal: string;
    match_score: number;
    posted_date: string;
    salary?: string;
  };
  onApplicationStart?: (applicationId: string) => void;
  onApplicationComplete?: (applicationId: string, success: boolean) => void;
}

const JobCard: React.FC<JobCardProps> = ({
  job,
  onApplicationStart,
  onApplicationComplete
}) => {
  const getMatchScoreColor = (score: number) => {
    if (score >= 90) return 'success';
    if (score >= 80) return 'info';
    if (score >= 70) return 'warning';
    return 'default';
  };

  const truncateDescription = (text: string, maxLength: number = 200) => {
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
  };

  return (
    <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <CardContent sx={{ flexGrow: 1 }}>
        {/* Header */}
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
          <Box flexGrow={1}>
            <Typography variant="h6" component="h3" gutterBottom>
              {job.title}
            </Typography>
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <BusinessIcon fontSize="small" color="action" />
              <Typography variant="body2" color="text.secondary">
                {job.company}
              </Typography>
            </Box>
            <Box display="flex" alignItems="center" gap={1}>
              <LocationIcon fontSize="small" color="action" />
              <Typography variant="body2" color="text.secondary">
                {job.location}
              </Typography>
            </Box>
          </Box>
          
          {/* Match Score */}
          <Box display="flex" flexDirection="column" alignItems="center" ml={2}>
            <Chip
              icon={<TrendingUpIcon />}
              label={`${job.match_score}%`}
              color={getMatchScoreColor(job.match_score)}
              variant="filled"
              size="small"
            />
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
              Match
            </Typography>
          </Box>
        </Box>

        {/* Salary */}
        {job.salary && (
          <Box mb={2}>
            <Typography variant="body2" color="primary" fontWeight="medium">
              {job.salary}
            </Typography>
          </Box>
        )}

        {/* Description */}
        <Typography variant="body2" color="text.secondary" paragraph>
          {truncateDescription(job.description)}
        </Typography>

        {/* Portal and Posted Date */}
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Chip
            label={job.portal}
            size="small"
            variant="outlined"
            sx={{ textTransform: 'capitalize' }}
          />
          <Typography variant="caption" color="text.secondary">
            {new Date(job.posted_date).toLocaleDateString()}
          </Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        {/* Actions */}
        <Box display="flex" gap={2} alignItems="center">
          <Box flexGrow={1}>
            <AutoApplyButton
              jobId={job.id}
              jobTitle={job.title}
              company={job.company}
              matchScore={job.match_score}
              onApplicationStart={onApplicationStart}
              onApplicationComplete={onApplicationComplete}
            />
          </Box>
          
          <Link
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              textDecoration: 'none',
              color: 'primary.main',
              '&:hover': {
                textDecoration: 'underline',
              },
            }}
          >
            <Typography variant="body2">
              View Job
            </Typography>
            <OpenInNewIcon fontSize="small" />
          </Link>
        </Box>
      </CardContent>
    </Card>
  );
};

export default JobCard;