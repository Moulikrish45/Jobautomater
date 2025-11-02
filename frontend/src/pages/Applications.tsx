import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  IconButton,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid,
  Pagination,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  Edit as EditIcon,
  FilterList as FilterIcon,
} from '@mui/icons-material';
import { format, parseISO } from 'date-fns';
import {
  ApplicationSummary,
  ApplicationDetail,
  ApplicationStatus,
  ApplicationOutcome,
  JobPortal,
} from '../types/api';
import DashboardAPI, { ApplicationFilters } from '../services/api';

const Applications: React.FC = () => {
  const [applications, setApplications] = useState<ApplicationSummary[]>([]);
  const [selectedApplication, setSelectedApplication] = useState<ApplicationDetail | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState<ApplicationFilters>({});

  // TODO: Get user ID from authentication context
  const userId = 'user123'; // Placeholder

  const itemsPerPage = 20;

  useEffect(() => {
    fetchApplications();
  }, [page, filters]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchApplications = async () => {
    try {
      setLoading(true);
      setError(null);

      const filterParams = {
        ...filters,
        limit: itemsPerPage,
        skip: (page - 1) * itemsPerPage,
      };

      const data = await DashboardAPI.getApplications(userId, filterParams);
      setApplications(data);
      
      // Calculate total pages (this would ideally come from the API)
      setTotalPages(Math.ceil(data.length / itemsPerPage));
    } catch (err) {
      console.error('Failed to fetch applications:', err);
      setError('Failed to load applications. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleViewDetails = async (applicationId: string) => {
    try {
      const detail = await DashboardAPI.getApplicationDetail(userId, applicationId);
      setSelectedApplication(detail);
      setDetailDialogOpen(true);
    } catch (err) {
      console.error('Failed to fetch application details:', err);
      setError('Failed to load application details.');
    }
  };

  const handleEditApplication = (application: ApplicationSummary) => {
    // Convert summary to detail format for editing
    setSelectedApplication({
      ...application,
      user_id: userId,
      job_id: '',
      job_url: '',
      updated_at: new Date().toISOString(),
      attempts: [],
      tags: [],
      job_details: {} as any,
    });
    setEditDialogOpen(true);
  };

  const handleUpdateOutcome = async (outcome: ApplicationOutcome, notes?: string) => {
    if (!selectedApplication) return;

    try {
      await DashboardAPI.updateApplicationOutcome(
        userId,
        selectedApplication.id,
        outcome,
        notes
      );
      setEditDialogOpen(false);
      fetchApplications(); // Refresh the list
    } catch (err) {
      console.error('Failed to update application outcome:', err);
      setError('Failed to update application outcome.');
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

  const getOutcomeColor = (outcome?: ApplicationOutcome) => {
    if (!outcome) return 'default';
    
    switch (outcome) {
      case ApplicationOutcome.OFFER_RECEIVED:
      case ApplicationOutcome.OFFER_ACCEPTED:
        return 'success';
      case ApplicationOutcome.REJECTED:
        return 'error';
      case ApplicationOutcome.INTERVIEW_SCHEDULED:
      case ApplicationOutcome.INTERVIEW_COMPLETED:
        return 'info';
      default:
        return 'default';
    }
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
          Applications
        </Typography>
        <Button
          startIcon={<FilterIcon />}
          onClick={() => setFilterDialogOpen(true)}
          variant="outlined"
        >
          Filters
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Card>
        <CardContent>
          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Job Title</TableCell>
                  <TableCell>Company</TableCell>
                  <TableCell>Portal</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Outcome</TableCell>
                  <TableCell>Match Score</TableCell>
                  <TableCell>Applied Date</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {applications.map((app) => (
                  <TableRow key={app.id}>
                    <TableCell>{app.job_title}</TableCell>
                    <TableCell>{app.company_name}</TableCell>
                    <TableCell>
                      <Chip label={app.portal} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={app.status.replace('_', ' ')}
                        size="small"
                        color={getStatusColor(app.status) as any}
                      />
                    </TableCell>
                    <TableCell>
                      {app.outcome ? (
                        <Chip
                          label={app.outcome.replace('_', ' ')}
                          size="small"
                          color={getOutcomeColor(app.outcome) as any}
                        />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>{Math.round(app.match_score * 100)}%</TableCell>
                    <TableCell>
                      {app.applied_at
                        ? format(parseISO(app.applied_at), 'MMM dd, yyyy')
                        : '-'}
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => handleViewDetails(app.id)}
                      >
                        <ViewIcon />
                      </IconButton>
                      <IconButton
                        size="small"
                        onClick={() => handleEditApplication(app)}
                      >
                        <EditIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {applications.length > 0 && (
            <Box display="flex" justifyContent="center" mt={2}>
              <Pagination
                count={totalPages}
                page={page}
                onChange={(_, newPage) => setPage(newPage)}
                color="primary"
              />
            </Box>
          )}
        </CardContent>
      </Card>

      {/* Application Detail Dialog */}
      <Dialog
        open={detailDialogOpen}
        onClose={() => setDetailDialogOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Application Details</DialogTitle>
        <DialogContent>
          {selectedApplication && (
            <Box>
              <Typography variant="h6" gutterBottom>
                {selectedApplication.job_title} at {selectedApplication.company_name}
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Status: {selectedApplication.status}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Portal: {selectedApplication.portal}
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Match Score: {Math.round(selectedApplication.match_score * 100)}%
                  </Typography>
                </Grid>
                <Grid item xs={6}>
                  <Typography variant="body2" color="text.secondary">
                    Attempts: {selectedApplication.total_attempts}
                  </Typography>
                </Grid>
              </Grid>
              {selectedApplication.notes && (
                <Box mt={2}>
                  <Typography variant="subtitle2">Notes:</Typography>
                  <Typography variant="body2">{selectedApplication.notes}</Typography>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDetailDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* Edit Application Dialog */}
      <Dialog
        open={editDialogOpen}
        onClose={() => setEditDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Update Application</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <FormControl fullWidth margin="normal">
              <InputLabel>Outcome</InputLabel>
              <Select
                value={selectedApplication?.outcome || ''}
                label="Outcome"
                onChange={(e) => {
                  if (selectedApplication) {
                    setSelectedApplication({
                      ...selectedApplication,
                      outcome: e.target.value as ApplicationOutcome,
                    });
                  }
                }}
              >
                {Object.values(ApplicationOutcome).map((outcome) => (
                  <MenuItem key={outcome} value={outcome}>
                    {outcome.replace('_', ' ')}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              fullWidth
              margin="normal"
              label="Notes"
              multiline
              rows={3}
              value={selectedApplication?.notes || ''}
              onChange={(e) => {
                if (selectedApplication) {
                  setSelectedApplication({
                    ...selectedApplication,
                    notes: e.target.value,
                  });
                }
              }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={() => {
              if (selectedApplication?.outcome) {
                handleUpdateOutcome(selectedApplication.outcome, selectedApplication.notes);
              }
            }}
            variant="contained"
          >
            Update
          </Button>
        </DialogActions>
      </Dialog>

      {/* Filter Dialog */}
      <Dialog
        open={filterDialogOpen}
        onClose={() => setFilterDialogOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle>Filter Applications</DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 1 }}>
            <FormControl fullWidth margin="normal">
              <InputLabel>Status</InputLabel>
              <Select
                multiple
                value={filters.status || []}
                label="Status"
                onChange={(e) => {
                  setFilters({
                    ...filters,
                    status: e.target.value as ApplicationStatus[],
                  });
                }}
              >
                {Object.values(ApplicationStatus).map((status) => (
                  <MenuItem key={status} value={status}>
                    {status.replace('_', ' ')}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel>Portal</InputLabel>
              <Select
                multiple
                value={filters.portal || []}
                label="Portal"
                onChange={(e) => {
                  setFilters({
                    ...filters,
                    portal: e.target.value as JobPortal[],
                  });
                }}
              >
                {Object.values(JobPortal).map((portal) => (
                  <MenuItem key={portal} value={portal}>
                    {portal}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              fullWidth
              margin="normal"
              label="Company"
              value={filters.company || ''}
              onChange={(e) => {
                setFilters({
                  ...filters,
                  company: e.target.value,
                });
              }}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFilters({})}>Clear</Button>
          <Button onClick={() => setFilterDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={() => {
              setFilterDialogOpen(false);
              setPage(1);
              fetchApplications();
            }}
            variant="contained"
          >
            Apply Filters
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default Applications;