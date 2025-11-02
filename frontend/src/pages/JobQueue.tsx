import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  CardActions,
  Grid,
  Button,
  Chip,
  LinearProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  CircularProgress,
  Alert,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Launch as LaunchIcon,
  Block as SkipIcon,
  LocationOn as LocationIcon,
  Business as CompanyIcon,
} from '@mui/icons-material';
import { format, parseISO } from 'date-fns';
import { JobQueueItem } from '../types/api';
import DashboardAPI from '../services/api';

const JobQueue: React.FC = () => {
  const [jobs, setJobs] = useState<JobQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [skipDialogOpen, setSkipDialogOpen] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobQueueItem | null>(null);
  const [skipReason, setSkipReason] = useState('');

  // TODO: Get user ID from authentication context
  const userId = 'user123'; // Placeholder

  useEffect(() => {
    fetchJobQueue();
  }, []);

  const fetchJobQueue = async () => {
    try {
      setLoading(true);
      setError(null);

      const data = await DashboardAPI.getJobQueue(userId, 50);
      setJobs(data);
    } catch (err) {
      console.error('Failed to fetch job queue:', err);
      setError('Failed to load job queue. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSkipJob = (job: JobQueueItem) => {
    setSelectedJob(job);
    setSkipDialogOpen(true);
  };

  const confirmSkipJob = async () => {
    if (!selectedJob) return;

    try {
      await DashboardAPI.skipJob(userId, selectedJob.id, skipReason);
      setSkipDialogOpen(false);
      setSkipReason('');
      setSelectedJob(null);
      
      // Remove the job from the list
      setJobs(jobs.filter(job => job.id !== selectedJob.id));
    } catch (err) {
      console.error('Failed to skip job:', err);
      setError('Failed to skip job. Please try again.');
    }
  };

  const getPortalColor = (portal: string) => {
    switch (portal.toLowerCase()) {
      case 'linkedin':
        return 'primary';
      case 'indeed':
        return 'secondary';
      case 'naukri':
        return 'success';
      default:
        return 'default';
    }
  };

  const getMatchScoreColor = (score: number) => {
    if (score >= 0.8) return 'success';
    if (score >= 0.6) return 'warning';
    return 'error';
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Job Queue
        </Typography>
        <Button onClick={fetchJobQueue} variant="outlined">
          Refresh
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      {jobs.length === 0 ? (
        <Card>
          <CardContent>
            <Typography variant="h6" color="text.secondary" textAlign="center">
              No jobs in queue
            </Typography>
            <Typography variant="body2" color="text.secondary" textAlign="center">
              Jobs will appear here when they are discovered and queued for application.
            </Typography>
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          {jobs.map((job) => (
            <Grid item xs={12} md={6} lg={4} key={job.id}>
              <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Typography variant="h6" component="h2" sx={{ flexGrow: 1, mr: 1 }}>
                      {job.title}
                    </Typography>
                    <Chip
                      label={job.portal}
                      size="small"
                      color={getPortalColor(job.portal) as any}
                    />
                  </Box>

                  <Box display="flex" alignItems="center" mb={1}>
                    <CompanyIcon fontSize="small" color="action" />
                    <Typography variant="body2" color="text.secondary" ml={1}>
                      {job.company}
                    </Typography>
                  </Box>

                  <Box display="flex" alignItems="center" mb={2}>
                    <LocationIcon fontSize="small" color="action" />
                    <Typography variant="body2" color="text.secondary" ml={1}>
                      {job.location.city && job.location.state
                        ? `${job.location.city}, ${job.location.state}`
                        : job.location.country}
                      {job.location.is_remote && ' (Remote)'}
                      {job.location.is_hybrid && ' (Hybrid)'}
                    </Typography>
                  </Box>

                  <Box mb={2}>
                    <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                      <Typography variant="body2" color="text.secondary">
                        Match Score
                      </Typography>
                      <Typography
                        variant="body2"
                        color={`${getMatchScoreColor(job.match_score)}.main`}
                        fontWeight="bold"
                      >
                        {Math.round(job.match_score * 100)}%
                      </Typography>
                    </Box>
                    <LinearProgress
                      variant="determinate"
                      value={job.match_score * 100}
                      color={getMatchScoreColor(job.match_score) as any}
                      sx={{ height: 6, borderRadius: 3 }}
                    />
                  </Box>

                  <Typography variant="caption" color="text.secondary">
                    Discovered: {format(parseISO(job.discovered_at), 'MMM dd, yyyy HH:mm')}
                  </Typography>
                </CardContent>

                <CardActions>
                  <Tooltip title="View job posting">
                    <IconButton
                      size="small"
                      onClick={() => window.open(job.url, '_blank')}
                    >
                      <LaunchIcon />
                    </IconButton>
                  </Tooltip>
                  <Button
                    size="small"
                    startIcon={<SkipIcon />}
                    onClick={() => handleSkipJob(job)}
                    color="error"
                  >
                    Skip
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Skip Job Dialog */}
      <Dialog
        open={skipDialogOpen}
        onClose={() => setSkipDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Skip Job</DialogTitle>
        <DialogContent>
          {selectedJob && (
            <Box>
              <Typography variant="body1" gutterBottom>
                Are you sure you want to skip this job?
              </Typography>
              <Typography variant="h6" color="primary" gutterBottom>
                {selectedJob.title} at {selectedJob.company}
              </Typography>
              <TextField
                fullWidth
                margin="normal"
                label="Reason (optional)"
                multiline
                rows={3}
                value={skipReason}
                onChange={(e) => setSkipReason(e.target.value)}
                placeholder="Why are you skipping this job?"
              />
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSkipDialogOpen(false)}>Cancel</Button>
          <Button onClick={confirmSkipJob} color="error" variant="contained">
            Skip Job
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default JobQueue;