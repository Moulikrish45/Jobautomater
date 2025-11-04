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
  Tooltip,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  Edit as EditIcon,
  FilterList as FilterIcon,
  Refresh as RefreshIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  PlayArrow as PlayIcon,
} from '@mui/icons-material';
import { format, parseISO } from 'date-fns';
import { useAuth } from '../contexts/AuthContext';
import ApplicationDetail from '../components/ApplicationDetail';

interface ApplicationData {
  id: string;
  job_id: string;
  status: 'pending' | 'queued' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  outcome?: 'applied' | 'viewed' | 'rejected' | 'interview_scheduled' | 'interview_completed' | 'offer_received' | 'offer_accepted' | 'offer_declined';
  applied_at?: string;
  created_at: string;
  total_attempts: number;
  successful_attempts: number;
  notes?: string;
  tags: string[];
}

interface ApplicationFilters {
  status?: string[];
  outcome?: string[];
  limit?: number;
  skip?: number;
}

const Applications: React.FC = () => {
  const { token } = useAuth();
  const [applications, setApplications] = useState<ApplicationData[]>([]);
  const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null);
  const [detailDialogOpen, setDetailDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [filterDialogOpen, setFilterDialogOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState<ApplicationFilters>({});
  const [editingApplication, setEditingApplication] = useState<ApplicationData | null>(null);
  const [editOutcome, setEditOutcome] = useState<string>('');
  const [editNotes, setEditNotes] = useState<string>('');

  const itemsPerPage = 20;

  useEffect(() => {
    fetchApplications();
  }, [page, filters]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchApplications = async () => {
    if (!token) return;

    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (filters.status && filters.status.length > 0) {
        filters.status.forEach(status => params.append('status_filter', status));
      }
      if (filters.outcome && filters.outcome.length > 0) {
        filters.outcome.forEach(outcome => params.append('outcome_filter', outcome));
      }
      params.append('limit', itemsPerPage.toString());
      params.append('skip', ((page - 1) * itemsPerPage).toString());

      const response = await fetch(`http://localhost:8000/api/v1/applications/?${params}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch applications');
      }

      const data = await response.json();
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

  const handleViewDetails = (applicationId: string) => {
    setSelectedApplicationId(applicationId);
    setDetailDialogOpen(true);
  };

  const handleEditApplication = (application: ApplicationData) => {
    setEditingApplication(application);
    setEditOutcome(application.outcome || '');
    setEditNotes(application.notes || '');
    setEditDialogOpen(true);
  };

  const handleUpdateOutcome = async () => {
    if (!editingApplication || !token) return;

    try {
      const response = await fetch(`http://localhost:8000/api/v1/applications/${editingApplication.id}/outcome`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          outcome: editOutcome,
          notes: editNotes,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to update application outcome');
      }

      setEditDialogOpen(false);
      fetchApplications(); // Refresh the list
    } catch (err) {
      console.error('Failed to update application outcome:', err);
      setError('Failed to update application outcome.');
    }
  };

  const handleRetryApplication = async (applicationId: string) => {
    if (!token) return;

    try {
      const response = await fetch(`http://localhost:8000/api/v1/applications/${applicationId}/retry`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to retry application');
      }

      fetchApplications(); // Refresh the list
    } catch (err) {
      console.error('Failed to retry application:', err);
      setError('Failed to retry application.');
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'in_progress':
        return 'warning';
      case 'queued':
        return 'info';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckIcon fontSize="small" />;
      case 'failed':
        return <ErrorIcon fontSize="small" />;
      case 'in_progress':
        return <CircularProgress size={16} />;
      case 'queued':
        return <ScheduleIcon fontSize="small" />;
      default:
        return <PlayIcon fontSize="small" />;
    }
  };

  const getOutcomeColor = (outcome?: string) => {
    if (!outcome) return 'default';
    
    switch (outcome) {
      case 'offer_received':
      case 'offer_accepted':
        return 'success';
      case 'rejected':
        return 'error';
      case 'interview_scheduled':
      case 'interview_completed':
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
        <Box>
          <Button
            startIcon={<RefreshIcon />}
            onClick={fetchApplications}
            variant="outlined"
            sx={{ mr: 1 }}
          >
            Refresh
          </Button>
          <Button
            startIcon={<FilterIcon />}
            onClick={() => setFilterDialogOpen(true)}
            variant="outlined"
          >
            Filters
          </Button>
        </Box>
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
                  <TableCell>Status</TableCell>
                  <TableCell>Job ID</TableCell>
                  <TableCell>Outcome</TableCell>
                  <TableCell>Attempts</TableCell>
                  <TableCell>Applied Date</TableCell>
                  <TableCell>Created Date</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {applications.map((app) => (
                  <TableRow key={app.id}>
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        {getStatusIcon(app.status)}
                        <Chip
                          label={app.status.replace('_', ' ').toUpperCase()}
                          size="small"
                          color={getStatusColor(app.status) as any}
                          variant="filled"
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {app.job_id}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {app.outcome ? (
                        <Chip
                          label={app.outcome.replace('_', ' ').toUpperCase()}
                          size="small"
                          color={getOutcomeColor(app.outcome) as any}
                          variant="outlined"
                        />
                      ) : (
                        '-'
                      )}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {app.successful_attempts}/{app.total_attempts}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {app.applied_at
                        ? format(parseISO(app.applied_at), 'MMM dd, yyyy HH:mm')
                        : '-'}
                    </TableCell>
                    <TableCell>
                      {format(parseISO(app.created_at), 'MMM dd, yyyy HH:mm')}
                    </TableCell>
                    <TableCell>
                      <Tooltip title="View Details">
                        <IconButton
                          size="small"
                          onClick={() => handleViewDetails(app.id)}
                        >
                          <ViewIcon />
                        </IconButton>
                      </Tooltip>
                      <Tooltip title="Edit Outcome">
                        <IconButton
                          size="small"
                          onClick={() => handleEditApplication(app)}
                        >
                          <EditIcon />
                        </IconButton>
                      </Tooltip>
                      {app.status === 'failed' && (
                        <Tooltip title="Retry Application">
                          <IconButton
                            size="small"
                            onClick={() => handleRetryApplication(app.id)}
                            color="primary"
                          >
                            <RefreshIcon />
                          </IconButton>
                        </Tooltip>
                      )}
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
      {selectedApplicationId && (
        <ApplicationDetail
          applicationId={selectedApplicationId}
          open={detailDialogOpen}
          onClose={() => {
            setDetailDialogOpen(false);
            setSelectedApplicationId(null);
          }}
        />
      )}

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
                value={editOutcome}
                label="Outcome"
                onChange={(e) => setEditOutcome(e.target.value)}
              >
                <MenuItem value="">None</MenuItem>
                <MenuItem value="applied">Applied</MenuItem>
                <MenuItem value="viewed">Viewed</MenuItem>
                <MenuItem value="rejected">Rejected</MenuItem>
                <MenuItem value="interview_scheduled">Interview Scheduled</MenuItem>
                <MenuItem value="interview_completed">Interview Completed</MenuItem>
                <MenuItem value="offer_received">Offer Received</MenuItem>
                <MenuItem value="offer_accepted">Offer Accepted</MenuItem>
                <MenuItem value="offer_declined">Offer Declined</MenuItem>
              </Select>
            </FormControl>
            <TextField
              fullWidth
              margin="normal"
              label="Notes"
              multiline
              rows={3}
              value={editNotes}
              onChange={(e) => setEditNotes(e.target.value)}
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setEditDialogOpen(false)}>Cancel</Button>
          <Button
            onClick={handleUpdateOutcome}
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
                    status: e.target.value as string[],
                  });
                }}
              >
                <MenuItem value="pending">Pending</MenuItem>
                <MenuItem value="queued">Queued</MenuItem>
                <MenuItem value="in_progress">In Progress</MenuItem>
                <MenuItem value="completed">Completed</MenuItem>
                <MenuItem value="failed">Failed</MenuItem>
                <MenuItem value="cancelled">Cancelled</MenuItem>
              </Select>
            </FormControl>
            <FormControl fullWidth margin="normal">
              <InputLabel>Outcome</InputLabel>
              <Select
                multiple
                value={filters.outcome || []}
                label="Outcome"
                onChange={(e) => {
                  setFilters({
                    ...filters,
                    outcome: e.target.value as string[],
                  });
                }}
              >
                <MenuItem value="applied">Applied</MenuItem>
                <MenuItem value="viewed">Viewed</MenuItem>
                <MenuItem value="rejected">Rejected</MenuItem>
                <MenuItem value="interview_scheduled">Interview Scheduled</MenuItem>
                <MenuItem value="interview_completed">Interview Completed</MenuItem>
                <MenuItem value="offer_received">Offer Received</MenuItem>
                <MenuItem value="offer_accepted">Offer Accepted</MenuItem>
                <MenuItem value="offer_declined">Offer Declined</MenuItem>
              </Select>
            </FormControl>
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