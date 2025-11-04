import React, { useState, useEffect } from 'react';
import {
  Button,
  CircularProgress,
  Box,
  Typography,
  Chip,
  Tooltip,
  LinearProgress,
  Alert,
  Snackbar
} from '@mui/material';
import {
  PlayArrow as PlayIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Schedule as ScheduleIcon,
  Refresh as RetryIcon
} from '@mui/icons-material';
import { useNotifications } from '../contexts/NotificationContext';
import { useAuth } from '../contexts/AuthContext';

export interface AutoApplyButtonProps {
  jobId: string;
  jobTitle: string;
  company: string;
  matchScore: number;
  disabled?: boolean;
  onApplicationStart?: (applicationId: string) => void;
  onApplicationComplete?: (applicationId: string, success: boolean) => void;
}

export interface ApplicationState {
  status: 'ready' | 'queued' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  currentStep: string;
  applicationId?: string;
  error?: string;
  confirmationNumber?: string;
}

const AutoApplyButton: React.FC<AutoApplyButtonProps> = ({
  jobId,
  jobTitle,
  company,
  matchScore,
  disabled = false,
  onApplicationStart,
  onApplicationComplete
}) => {
  const { token } = useAuth();
  const { addNotification } = useNotifications();
  
  const [applicationState, setApplicationState] = useState<ApplicationState>({
    status: 'ready',
    progress: 0,
    currentStep: '',
  });
  
  const [showError, setShowError] = useState(false);

  // Listen for WebSocket updates
  useEffect(() => {
    const handleWebSocketMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);
        
        // Check if this message is for our application
        if (message.data?.job_id === jobId || message.data?.application_id === applicationState.applicationId) {
          switch (message.type) {
            case 'application_queued':
              setApplicationState(prev => ({
                ...prev,
                status: 'queued',
                applicationId: message.data.application_id,
                progress: 5,
                currentStep: 'Queued for processing'
              }));
              break;
              
            case 'application_started':
              setApplicationState(prev => ({
                ...prev,
                status: 'in_progress',
                progress: 10,
                currentStep: 'Starting automation'
              }));
              if (onApplicationStart && message.data.application_id) {
                onApplicationStart(message.data.application_id);
              }
              break;
              
            case 'application_progress':
              setApplicationState(prev => ({
                ...prev,
                status: 'in_progress',
                progress: message.data.progress || prev.progress,
                currentStep: message.data.step || prev.currentStep
              }));
              break;
              
            case 'application_completed':
              const success = message.data.success !== false;
              setApplicationState(prev => ({
                ...prev,
                status: success ? 'completed' : 'failed',
                progress: success ? 100 : 0,
                currentStep: success ? 'Application submitted' : 'Application failed',
                confirmationNumber: message.data.confirmation_number,
                error: success ? undefined : message.data.error
              }));
              if (onApplicationComplete && applicationState.applicationId) {
                onApplicationComplete(applicationState.applicationId, success);
              }
              break;
              
            case 'application_failed':
              setApplicationState(prev => ({
                ...prev,
                status: 'failed',
                progress: 0,
                currentStep: 'Application failed',
                error: message.data.error || 'Unknown error occurred'
              }));
              setShowError(true);
              if (onApplicationComplete && applicationState.applicationId) {
                onApplicationComplete(applicationState.applicationId, false);
              }
              break;
          }
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    // This would be connected to the actual WebSocket in a real implementation
    // For now, we'll simulate it through the notification context
    
    return () => {
      // Cleanup WebSocket listener
    };
  }, [jobId, applicationState.applicationId, onApplicationStart, onApplicationComplete]);

  const handleApplyClick = async () => {
    if (!token) {
      addNotification({
        type: 'error',
        message: 'Please log in to apply for jobs',
      });
      return;
    }

    try {
      setApplicationState(prev => ({
        ...prev,
        status: 'queued',
        progress: 0,
        currentStep: 'Queueing application...'
      }));

      const response = await fetch('http://localhost:8000/api/v1/applications/queue', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          job_id: jobId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to queue application');
      }

      const data = await response.json();
      
      setApplicationState(prev => ({
        ...prev,
        applicationId: data.id,
        progress: 5,
        currentStep: 'Application queued successfully'
      }));

      addNotification({
        type: 'success',
        message: `Application queued for ${jobTitle}`,
      });

    } catch (error) {
      console.error('Failed to queue application:', error);
      
      setApplicationState(prev => ({
        ...prev,
        status: 'failed',
        error: error instanceof Error ? error.message : 'Failed to queue application'
      }));

      addNotification({
        type: 'error',
        message: `Failed to queue application: ${error instanceof Error ? error.message : 'Unknown error'}`,
      });
    }
  };

  const handleRetry = async () => {
    if (!applicationState.applicationId) {
      // If no application ID, treat as new application
      await handleApplyClick();
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/v1/applications/${applicationState.applicationId}/retry`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to retry application');
      }

      setApplicationState(prev => ({
        ...prev,
        status: 'queued',
        progress: 0,
        currentStep: 'Retrying application...',
        error: undefined
      }));

      addNotification({
        type: 'info',
        message: `Retrying application for ${jobTitle}`,
      });

    } catch (error) {
      console.error('Failed to retry application:', error);
      
      addNotification({
        type: 'error',
        message: `Failed to retry application: ${error instanceof Error ? error.message : 'Unknown error'}`,
      });
    }
  };

  const getButtonContent = () => {
    switch (applicationState.status) {
      case 'ready':
        return (
          <>
            <PlayIcon sx={{ mr: 1 }} />
            Auto-Apply
          </>
        );
        
      case 'queued':
        return (
          <>
            <ScheduleIcon sx={{ mr: 1 }} />
            Queued
          </>
        );
        
      case 'in_progress':
        return (
          <>
            <CircularProgress size={16} sx={{ mr: 1 }} />
            Applying...
          </>
        );
        
      case 'completed':
        return (
          <>
            <CheckIcon sx={{ mr: 1 }} />
            Applied
          </>
        );
        
      case 'failed':
        return (
          <>
            <RetryIcon sx={{ mr: 1 }} />
            Retry
          </>
        );
        
      default:
        return 'Auto-Apply';
    }
  };

  const getButtonColor = () => {
    switch (applicationState.status) {
      case 'ready':
        return 'primary';
      case 'queued':
        return 'info';
      case 'in_progress':
        return 'info';
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      default:
        return 'primary';
    }
  };

  const isButtonDisabled = () => {
    return disabled || applicationState.status === 'queued' || applicationState.status === 'in_progress';
  };

  const handleButtonClick = () => {
    if (applicationState.status === 'failed') {
      handleRetry();
    } else if (applicationState.status === 'ready') {
      handleApplyClick();
    }
  };

  // Don't show button for low match scores
  if (matchScore < 70) {
    return null;
  }

  return (
    <Box sx={{ minWidth: 200 }}>
      <Tooltip 
        title={
          applicationState.status === 'completed' && applicationState.confirmationNumber
            ? `Applied successfully! Confirmation: ${applicationState.confirmationNumber}`
            : applicationState.error || `Match Score: ${matchScore}%`
        }
      >
        <Button
          variant="contained"
          color={getButtonColor()}
          onClick={handleButtonClick}
          disabled={isButtonDisabled()}
          fullWidth
          sx={{
            minHeight: 40,
            textTransform: 'none',
            fontWeight: 600,
          }}
        >
          {getButtonContent()}
        </Button>
      </Tooltip>

      {/* Progress indicator */}
      {(applicationState.status === 'queued' || applicationState.status === 'in_progress') && (
        <Box sx={{ mt: 1 }}>
          <LinearProgress 
            variant="determinate" 
            value={applicationState.progress} 
            sx={{ height: 4, borderRadius: 2 }}
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
            {applicationState.currentStep}
          </Typography>
        </Box>
      )}

      {/* Success indicator */}
      {applicationState.status === 'completed' && (
        <Box sx={{ mt: 1 }}>
          <Chip
            icon={<CheckIcon />}
            label={`Applied to ${company}`}
            color="success"
            size="small"
            sx={{ fontSize: '0.75rem' }}
          />
          {applicationState.confirmationNumber && (
            <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5, display: 'block' }}>
              Confirmation: {applicationState.confirmationNumber}
            </Typography>
          )}
        </Box>
      )}

      {/* Error snackbar */}
      <Snackbar
        open={showError}
        autoHideDuration={6000}
        onClose={() => setShowError(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        <Alert 
          onClose={() => setShowError(false)} 
          severity="error" 
          variant="filled"
        >
          Application failed: {applicationState.error}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default AutoApplyButton;