import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Grid,
  Card,
  CardMedia,
  CardContent,
  IconButton,
  Tooltip,
  Alert,
  CircularProgress,
  Link
} from '@mui/material';
import {
  Close as CloseIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  PlayArrow as PlayIcon,
  ExpandMore as ExpandMoreIcon,
  OpenInNew as OpenInNewIcon,
  Download as DownloadIcon,
  Fullscreen as FullscreenIcon
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

// Simple Timeline components using basic MUI
const SimpleTimeline: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box sx={{ position: 'relative', pl: 2 }}>{children}</Box>
);

const SimpleTimelineItem: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box sx={{ display: 'flex', mb: 2 }}>{children}</Box>
);

const SimpleTimelineSeparator: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mr: 2 }}>
    {children}
  </Box>
);

const SimpleTimelineDot: React.FC<{ color?: string; children: React.ReactNode }> = ({ color = 'primary', children }) => (
  <Box
    sx={{
      width: 40,
      height: 40,
      borderRadius: '50%',
      bgcolor: `${color}.main`,
      color: 'white',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      mb: 1
    }}
  >
    {children}
  </Box>
);

const SimpleTimelineConnector: React.FC = () => (
  <Box
    sx={{
      width: 2,
      height: 30,
      bgcolor: 'grey.300',
      flexGrow: 1
    }}
  />
);

const SimpleTimelineContent: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <Box sx={{ flex: 1, pt: 1 }}>{children}</Box>
);

interface ApplicationDetailProps {
  applicationId: string;
  open: boolean;
  onClose: () => void;
}

interface ApplicationData {
  id: string;
  job_id: string;
  status: string;
  outcome?: string;
  applied_at?: string;
  created_at: string;
  total_attempts: number;
  successful_attempts: number;
  notes?: string;
  tags: string[];
  attempts: Array<{
    attempt_number: number;
    started_at: string;
    completed_at?: string;
    success: boolean;
    error_message?: string;
    screenshots: string[];
  }>;
  submission_data?: {
    confirmation_number?: string;
    form_data?: Record<string, any>;
    screenshots?: string[];
    error_message?: string;
    automation_logs?: string[];
  };
}

interface JobData {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  description: string;
  match_score: number;
}

const ApplicationDetail: React.FC<ApplicationDetailProps> = ({
  applicationId,
  open,
  onClose
}) => {
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [applicationData, setApplicationData] = useState<ApplicationData | null>(null);
  const [jobData, setJobData] = useState<JobData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedScreenshot, setSelectedScreenshot] = useState<string | null>(null);

  useEffect(() => {
    if (open && applicationId) {
      fetchApplicationDetails();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, applicationId]);

  const fetchApplicationDetails = async () => {
    if (!token) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`http://localhost:8000/api/v1/applications/${applicationId}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch application details');
      }

      const data = await response.json();
      setApplicationData(data.application);
      setJobData(data.job);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load application details');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'in_progress':
        return 'info';
      case 'queued':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckIcon />;
      case 'failed':
        return <ErrorIcon />;
      case 'in_progress':
        return <CircularProgress size={20} />;
      case 'queued':
        return <ScheduleIcon />;
      default:
        return <PlayIcon />;
    }
  };

  const formatDateTime = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const handleScreenshotClick = (screenshotUrl: string) => {
    setSelectedScreenshot(screenshotUrl);
  };

  const handleDownloadScreenshot = (screenshotUrl: string, filename: string) => {
    const link = document.createElement('a');
    link.href = screenshotUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  if (loading) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogContent>
          <Box display="flex" justifyContent="center" alignItems="center" minHeight={200}>
            <CircularProgress />
          </Box>
        </DialogContent>
      </Dialog>
    );
  }

  if (error) {
    return (
      <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
        <DialogTitle>Error</DialogTitle>
        <DialogContent>
          <Alert severity="error">{error}</Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Close</Button>
        </DialogActions>
      </Dialog>
    );
  }

  if (!applicationData || !jobData) {
    return null;
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} maxWidth="lg" fullWidth>
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">
              Application Details - {jobData.title}
            </Typography>
            <IconButton onClick={onClose}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>

        <DialogContent dividers>
          {/* Application Status */}
          <Box mb={3}>
            <Typography variant="h6" gutterBottom>
              Status
            </Typography>
            <Box display="flex" alignItems="center" gap={2}>
              <Chip
                icon={getStatusIcon(applicationData.status)}
                label={applicationData.status.toUpperCase()}
                color={getStatusColor(applicationData.status)}
                variant="filled"
              />
              {applicationData.outcome && (
                <Chip
                  label={applicationData.outcome.replace('_', ' ').toUpperCase()}
                  variant="outlined"
                />
              )}
            </Box>
          </Box>

          {/* Job Information */}
          <Box mb={3}>
            <Typography variant="h6" gutterBottom>
              Job Information
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">Company</Typography>
                <Typography variant="body1">{jobData.company}</Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">Location</Typography>
                <Typography variant="body1">{jobData.location}</Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">Match Score</Typography>
                <Typography variant="body1">{jobData.match_score}%</Typography>
              </Grid>
              <Grid item xs={12} md={6}>
                <Typography variant="body2" color="text.secondary">Job URL</Typography>
                <Link href={jobData.url} target="_blank" rel="noopener">
                  View Job Posting <OpenInNewIcon fontSize="small" />
                </Link>
              </Grid>
            </Grid>
          </Box>

          {/* Application Timeline */}
          <Box mb={3}>
            <Typography variant="h6" gutterBottom>
              Application Timeline
            </Typography>
            <SimpleTimeline>
              <SimpleTimelineItem>
                <SimpleTimelineSeparator>
                  <SimpleTimelineDot color="primary">
                    <PlayIcon />
                  </SimpleTimelineDot>
                  <SimpleTimelineConnector />
                </SimpleTimelineSeparator>
                <SimpleTimelineContent>
                  <Typography variant="body1">Application Created</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {formatDateTime(applicationData.created_at)}
                  </Typography>
                </SimpleTimelineContent>
              </SimpleTimelineItem>

              {applicationData.applied_at && (
                <SimpleTimelineItem>
                  <SimpleTimelineSeparator>
                    <SimpleTimelineDot color="success">
                      <CheckIcon />
                    </SimpleTimelineDot>
                    <SimpleTimelineConnector />
                  </SimpleTimelineSeparator>
                  <SimpleTimelineContent>
                    <Typography variant="body1">Application Submitted</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {formatDateTime(applicationData.applied_at)}
                    </Typography>
                    {applicationData.submission_data?.confirmation_number && (
                      <Typography variant="body2" color="primary">
                        Confirmation: {applicationData.submission_data.confirmation_number}
                      </Typography>
                    )}
                  </SimpleTimelineContent>
                </SimpleTimelineItem>
              )}
            </SimpleTimeline>
          </Box>

          {/* Screenshots */}
          {applicationData.submission_data?.screenshots && applicationData.submission_data.screenshots.length > 0 && (
            <Box mb={3}>
              <Typography variant="h6" gutterBottom>
                Application Screenshots
              </Typography>
              <Grid container spacing={2}>
                {applicationData.submission_data.screenshots.map((screenshot, index) => (
                  <Grid item xs={12} sm={6} md={4} key={index}>
                    <Card>
                      <CardMedia
                        component="img"
                        height="200"
                        image={`http://localhost:8000${screenshot}`}
                        alt={`Screenshot ${index + 1}`}
                        sx={{ cursor: 'pointer' }}
                        onClick={() => handleScreenshotClick(`http://localhost:8000${screenshot}`)}
                      />
                      <CardContent sx={{ p: 1 }}>
                        <Box display="flex" justifyContent="space-between" alignItems="center">
                          <Typography variant="caption">
                            Screenshot {index + 1}
                          </Typography>
                          <Box>
                            <Tooltip title="View Full Size">
                              <IconButton
                                size="small"
                                onClick={() => handleScreenshotClick(`http://localhost:8000${screenshot}`)}
                              >
                                <FullscreenIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title="Download">
                              <IconButton
                                size="small"
                                onClick={() => handleDownloadScreenshot(
                                  `http://localhost:8000${screenshot}`,
                                  `screenshot_${index + 1}.png`
                                )}
                              >
                                <DownloadIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          </Box>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Box>
          )}

          {/* Application Attempts */}
          {applicationData.attempts && applicationData.attempts.length > 0 && (
            <Box mb={3}>
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">
                    Application Attempts ({applicationData.attempts.length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  {applicationData.attempts.map((attempt, index) => (
                    <Box key={index} mb={2} p={2} border={1} borderColor="divider" borderRadius={1}>
                      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                        <Typography variant="subtitle2">
                          Attempt {attempt.attempt_number}
                        </Typography>
                        <Chip
                          label={attempt.success ? 'Success' : 'Failed'}
                          color={attempt.success ? 'success' : 'error'}
                          size="small"
                        />
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        Started: {formatDateTime(attempt.started_at)}
                      </Typography>
                      {attempt.completed_at && (
                        <Typography variant="body2" color="text.secondary">
                          Completed: {formatDateTime(attempt.completed_at)}
                        </Typography>
                      )}
                      {attempt.error_message && (
                        <Alert severity="error" sx={{ mt: 1 }}>
                          {attempt.error_message}
                        </Alert>
                      )}
                    </Box>
                  ))}
                </AccordionDetails>
              </Accordion>
            </Box>
          )}

          {/* Automation Logs */}
          {applicationData.submission_data?.automation_logs && applicationData.submission_data.automation_logs.length > 0 && (
            <Box mb={3}>
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">
                    Automation Logs ({applicationData.submission_data.automation_logs.length})
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box
                    sx={{
                      maxHeight: 300,
                      overflow: 'auto',
                      backgroundColor: 'grey.100',
                      p: 2,
                      borderRadius: 1,
                      fontFamily: 'monospace',
                      fontSize: '0.875rem'
                    }}
                  >
                    {applicationData.submission_data.automation_logs.map((log, index) => (
                      <Typography key={index} variant="body2" component="div">
                        {log}
                      </Typography>
                    ))}
                  </Box>
                </AccordionDetails>
              </Accordion>
            </Box>
          )}

          {/* Form Data */}
          {applicationData.submission_data?.form_data && (
            <Box mb={3}>
              <Accordion>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="h6">Form Data Submitted</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <Box
                    sx={{
                      backgroundColor: 'grey.50',
                      p: 2,
                      borderRadius: 1,
                      fontFamily: 'monospace',
                      fontSize: '0.875rem'
                    }}
                  >
                    <pre>{JSON.stringify(applicationData.submission_data.form_data, null, 2)}</pre>
                  </Box>
                </AccordionDetails>
              </Accordion>
            </Box>
          )}
        </DialogContent>

        <DialogActions>
          <Button onClick={onClose} variant="contained">
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Screenshot Modal */}
      <Dialog
        open={!!selectedScreenshot}
        onClose={() => setSelectedScreenshot(null)}
        maxWidth="lg"
        fullWidth
      >
        <DialogTitle>
          <Box display="flex" justifyContent="space-between" alignItems="center">
            <Typography variant="h6">Screenshot</Typography>
            <IconButton onClick={() => setSelectedScreenshot(null)}>
              <CloseIcon />
            </IconButton>
          </Box>
        </DialogTitle>
        <DialogContent>
          {selectedScreenshot && (
            <Box display="flex" justifyContent="center">
              <img
                src={selectedScreenshot}
                alt="Full size screenshot"
                style={{ maxWidth: '100%', height: 'auto' }}
              />
            </Box>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
};

export default ApplicationDetail;