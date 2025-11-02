import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Chip,
  Tooltip,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Description as ResumeIcon,
  Search as SearchIcon,
  Assignment as ApplicationsIcon,
  Queue as QueueIcon,
  Settings as SettingsIcon,
  Wifi as ConnectedIcon,
  WifiOff as DisconnectedIcon,
} from '@mui/icons-material';
import { useNotifications } from '../contexts/NotificationContext';

const Navbar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { webSocketConnectionState } = useNotifications();

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <DashboardIcon /> },
    { path: '/resume', label: 'Upload Resume', icon: <ResumeIcon /> },
    { path: '/search', label: 'Search Jobs', icon: <SearchIcon /> },
    { path: '/applications', label: 'Applications', icon: <ApplicationsIcon /> },
    { path: '/queue', label: 'Job Queue', icon: <QueueIcon /> },
    { path: '/settings', label: 'Settings', icon: <SettingsIcon /> },
  ];

  const getConnectionStatus = () => {
    switch (webSocketConnectionState) {
      case 'connected':
        return { color: 'success', label: 'Connected', icon: <ConnectedIcon /> };
      case 'connecting':
        return { color: 'warning', label: 'Connecting', icon: <ConnectedIcon /> };
      case 'error':
        return { color: 'error', label: 'Error', icon: <DisconnectedIcon /> };
      default:
        return { color: 'default', label: 'Disconnected', icon: <DisconnectedIcon /> };
    }
  };

  const connectionStatus = getConnectionStatus();

  return (
    <AppBar 
      position="static" 
      elevation={0}
      sx={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderBottom: '1px solid rgba(255,255,255,0.1)'
      }}
    >
      <Toolbar sx={{ py: 1 }}>
        <Typography 
          variant="h5" 
          component="div" 
          sx={{ 
            flexGrow: 1, 
            fontWeight: 700,
            letterSpacing: '-0.5px'
          }}
        >
          🚀 JobBot
        </Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {navItems.map((item) => (
            <Button
              key={item.path}
              color="inherit"
              startIcon={item.icon}
              onClick={() => navigate(item.path)}
              sx={{
                backgroundColor: location.pathname === item.path ? 'rgba(255, 255, 255, 0.2)' : 'transparent',
                borderRadius: 2,
                px: 2,
                '&:hover': {
                  backgroundColor: 'rgba(255, 255, 255, 0.15)'
                }
              }}
            >
              {item.label}
            </Button>
          ))}
          
          <Tooltip title={`Real-time updates: ${connectionStatus.label}`}>
            <Chip
              icon={connectionStatus.icon}
              label={connectionStatus.label}
              size="small"
              color={connectionStatus.color as any}
              variant="outlined"
              sx={{ 
                color: 'white',
                borderColor: 'rgba(255, 255, 255, 0.5)',
                '& .MuiChip-icon': { color: 'white' }
              }}
            />
          </Tooltip>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;