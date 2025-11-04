import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  IconButton,
  Badge,
  Tooltip,
  useTheme,
  useMediaQuery,
  Breadcrumbs,
  Link,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Notifications as NotificationsIcon,
  Brightness4 as DarkModeIcon,
  Brightness7 as LightModeIcon,
  Home as HomeIcon,
  Wifi as ConnectedIcon,
  WifiOff as DisconnectedIcon,
} from '@mui/icons-material';
import { useLocation } from 'react-router-dom';
import { useNotifications } from '../contexts/NotificationContext';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';

interface NavbarProps {
  onMenuClick: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ onMenuClick }) => {
  const location = useLocation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('lg'));
  const { notifications, webSocketConnectionState } = useNotifications();
  const { isDarkMode, toggleTheme } = useCustomTheme();
  
  const [notificationMenuOpen, setNotificationMenuOpen] = useState(false);

  const getConnectionStatus = () => {
    switch (webSocketConnectionState) {
      case 'connected':
        return { color: '#10b981', label: 'Connected', icon: <ConnectedIcon /> };
      case 'connecting':
        return { color: '#f59e0b', label: 'Connecting', icon: <ConnectedIcon /> };
      case 'error':
        return { color: '#ef4444', label: 'Error', icon: <DisconnectedIcon /> };
      default:
        return { color: '#6b7280', label: 'Offline', icon: <DisconnectedIcon /> };
    }
  };

  const connectionStatus = getConnectionStatus();

  const getPageTitle = (pathname: string) => {
    switch (pathname) {
      case '/': return 'Dashboard';
      case '/resume': return 'Resume';
      case '/search': return 'Job Search';
      case '/applications': return 'Applications';
      case '/queue': return 'Queue';
      case '/settings': return 'Settings';
      default: return 'Dashboard';
    }
  };

  const unreadNotifications = notifications.filter(n => !n.autoHide).length;

  return (
    <AppBar 
      position="sticky" 
      elevation={0}
      sx={{
        background: isDarkMode 
          ? 'rgba(15, 15, 35, 0.95)'
          : 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderBottom: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
        zIndex: theme.zIndex.drawer + 1,
      }}
    >
      <Toolbar sx={{ px: 3, py: 1 }}>
        {/* Mobile Menu Button */}
        {isMobile && (
          <IconButton
            color="inherit"
            onClick={onMenuClick}
            sx={{
              mr: 2,
              backgroundColor: isDarkMode 
                ? 'rgba(255, 255, 255, 0.1)'
                : 'rgba(0, 0, 0, 0.1)',
              borderRadius: '12px',
              '&:hover': {
                backgroundColor: isDarkMode 
                  ? 'rgba(255, 255, 255, 0.15)'
                  : 'rgba(0, 0, 0, 0.15)',
              }
            }}
          >
            <MenuIcon />
          </IconButton>
        )}

        {/* Page Title & Breadcrumbs */}
        <Box sx={{ flexGrow: 1 }}>
          <Typography 
            variant="h6" 
            sx={{ 
              fontWeight: 600,
              color: 'text.primary',
              mb: 0.15,
              fontSize: '1.125rem'
            }}
          >
            {getPageTitle(location.pathname)}
          </Typography>
          <Breadcrumbs 
            aria-label="breadcrumb"
            sx={{ 
              '& .MuiBreadcrumbs-separator': { 
                color: 'text.secondary' 
              }
            }}
          >
            <Link 
              color="text.secondary" 
              href="/" 
              sx={{ 
                display: 'flex', 
                alignItems: 'center',
                textDecoration: 'none',
                '&:hover': { color: 'primary.main' }
              }}
            >
              <HomeIcon sx={{ mr: 0.5, fontSize: 16 }} />
              Home
            </Link>
            {location.pathname !== '/' && (
              <Typography color="primary.main" sx={{ fontWeight: 500 }}>
                {getPageTitle(location.pathname)}
              </Typography>
            )}
          </Breadcrumbs>
        </Box>

        {/* Right Side Actions */}
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {/* Connection Status */}
          <Tooltip title={`Real-time updates: ${connectionStatus.label}`}>
            <IconButton
              color="inherit"
              sx={{
                backgroundColor: isDarkMode 
                  ? 'rgba(255, 255, 255, 0.1)'
                  : 'rgba(0, 0, 0, 0.1)',
                borderRadius: '12px',
                '&:hover': {
                  backgroundColor: isDarkMode 
                    ? 'rgba(255, 255, 255, 0.15)'
                    : 'rgba(0, 0, 0, 0.15)',
                }
              }}
            >
              {React.cloneElement(connectionStatus.icon, { 
                sx: { color: connectionStatus.color } 
              })}
            </IconButton>
          </Tooltip>

          {/* Theme Toggle */}
          <Tooltip title={isDarkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}>
            <IconButton
              onClick={toggleTheme}
              color="inherit"
              sx={{
                backgroundColor: isDarkMode 
                  ? 'rgba(255, 255, 255, 0.1)'
                  : 'rgba(0, 0, 0, 0.1)',
                borderRadius: '12px',
                '&:hover': {
                  backgroundColor: isDarkMode 
                    ? 'rgba(255, 255, 255, 0.15)'
                    : 'rgba(0, 0, 0, 0.15)',
                }
              }}
            >
              {isDarkMode ? <LightModeIcon /> : <DarkModeIcon />}
            </IconButton>
          </Tooltip>

          {/* Notifications */}
          <Tooltip title="Notifications">
            <IconButton
              color="inherit"
              onClick={() => setNotificationMenuOpen(!notificationMenuOpen)}
              sx={{
                backgroundColor: isDarkMode 
                  ? 'rgba(255, 255, 255, 0.1)'
                  : 'rgba(0, 0, 0, 0.1)',
                borderRadius: '12px',
                '&:hover': {
                  backgroundColor: isDarkMode
                    ? 'rgba(255, 255, 255, 0.15)'
                    : 'rgba(0, 0, 0, 0.15)',
                }
              }}
            >
              <Badge badgeContent={unreadNotifications} color="error">
                <NotificationsIcon />
              </Badge>
            </IconButton>
          </Tooltip>
        </Box>
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;