import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { Snackbar, Alert, AlertColor } from '@mui/material';
import { useWebSocket, WebSocketMessage } from '../hooks/useWebSocket';

export interface Notification {
  id: string;
  type: AlertColor;
  message: string;
  timestamp: Date;
  autoHide?: boolean;
  duration?: number;
}

export interface NotificationContextType {
  notifications: Notification[];
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp'>) => void;
  removeNotification: (id: string) => void;
  clearNotifications: () => void;
  isWebSocketConnected: boolean;
  webSocketConnectionState: string;
}

const NotificationContext = createContext<NotificationContextType | undefined>(undefined);

export const useNotifications = () => {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
};

interface NotificationProviderProps {
  children: React.ReactNode;
  userId: string;
}

export const NotificationProvider: React.FC<NotificationProviderProps> = ({
  children,
  userId,
}) => {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [currentSnackbar, setCurrentSnackbar] = useState<Notification | null>(null);

  const addNotification = useCallback((notification: Omit<Notification, 'id' | 'timestamp'>) => {
    const newNotification: Notification = {
      ...notification,
      id: Date.now().toString() + Math.random().toString(36).substring(2, 11),
      timestamp: new Date(),
      autoHide: notification.autoHide !== false,
      duration: notification.duration || 6000,
    };

    setNotifications(prev => [newNotification, ...prev].slice(0, 50)); // Keep last 50 notifications
    
    // Show in snackbar if auto-hide is enabled
    if (newNotification.autoHide) {
      setCurrentSnackbar(newNotification);
    }
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
    if (currentSnackbar?.id === id) {
      setCurrentSnackbar(null);
    }
  }, [currentSnackbar]);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
    setCurrentSnackbar(null);
  }, []);

  // WebSocket message handler
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    console.log('Received WebSocket message:', message);

    let notificationType: AlertColor = 'info';
    let notificationMessage = message.message || 'Unknown notification';
    let autoHide = true;

    switch (message.type) {
      case 'application_update':
        const status = message.data?.status;
        if (status === 'completed') {
          notificationType = 'success';
          notificationMessage = `Application completed: ${message.data?.job_title}`;
        } else if (status === 'failed') {
          notificationType = 'error';
          notificationMessage = `Application failed: ${message.data?.job_title}`;
          autoHide = false; // Keep error notifications visible
        } else if (status === 'in_progress') {
          notificationType = 'info';
          notificationMessage = `Application in progress: ${message.data?.job_title}`;
        }
        break;

      case 'job_discovered':
        notificationType = 'info';
        notificationMessage = `New job found: ${message.data?.title} at ${message.data?.company}`;
        break;

      case 'system_error':
        notificationType = 'error';
        notificationMessage = `System error: ${message.data?.error_message}`;
        autoHide = false;
        break;

      case 'progress_update':
        notificationType = 'info';
        const progress = Math.round((message.data?.progress || 0) * 100);
        notificationMessage = `${message.data?.operation}: ${progress}% complete`;
        break;

      case 'automation_status':
        notificationType = message.data?.enabled ? 'success' : 'warning';
        notificationMessage = `Automation ${message.data?.enabled ? 'enabled' : 'disabled'}`;
        break;

      case 'connection_established':
        notificationType = 'success';
        notificationMessage = 'Real-time updates connected';
        break;

      case 'ping':
        // Don't show ping messages as notifications
        return;

      default:
        notificationType = 'info';
        break;
    }

    addNotification({
      type: notificationType,
      message: notificationMessage,
      autoHide,
    });
  }, [addNotification]);

  // WebSocket connection
  const {
    isConnected: isWebSocketConnected,
    connectionState: webSocketConnectionState,
  } = useWebSocket(userId, {
    onMessage: handleWebSocketMessage,
    onConnect: () => {
      addNotification({
        type: 'success',
        message: 'Real-time updates connected',
        autoHide: true,
        duration: 2000,
      });
    },
    onDisconnect: () => {
      // Only show disconnect message if we were actually connected
      addNotification({
        type: 'info',
        message: 'Real-time updates offline',
        autoHide: true,
        duration: 2000,
      });
    },
    onError: () => {
      addNotification({
        type: 'warning',
        message: 'Real-time updates unavailable - working in offline mode',
        autoHide: true,
        duration: 4000,
      });
    },
  });

  // Auto-remove notifications after their duration
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setNotifications(prev => 
        prev.filter(notification => {
          if (!notification.autoHide) return true;
          const age = now.getTime() - notification.timestamp.getTime();
          return age < (notification.duration || 6000);
        })
      );
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const handleSnackbarClose = () => {
    setCurrentSnackbar(null);
  };

  const contextValue: NotificationContextType = {
    notifications,
    addNotification,
    removeNotification,
    clearNotifications,
    isWebSocketConnected,
    webSocketConnectionState,
  };

  return (
    <NotificationContext.Provider value={contextValue}>
      {children}
      
      {/* Snackbar for auto-hide notifications */}
      <Snackbar
        open={!!currentSnackbar}
        autoHideDuration={currentSnackbar?.duration || 6000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      >
        {currentSnackbar ? (
          <Alert
            onClose={handleSnackbarClose}
            severity={currentSnackbar.type}
            variant="filled"
          >
            {currentSnackbar.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </NotificationContext.Provider>
  );
};