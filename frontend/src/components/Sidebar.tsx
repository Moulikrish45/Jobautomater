import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Avatar,
  IconButton,
  useMediaQuery,
  Drawer,
  Fade,
  Collapse,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Description as ResumeIcon,
  Search as SearchIcon,
  Assignment as ApplicationsIcon,
  Queue as QueueIcon,
  Settings as SettingsIcon,
  AccountCircle as AccountIcon,
  Logout as LogoutIcon,
  Close as CloseIcon,
  ExpandMore as ExpandMoreIcon,
} from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';
import { useTheme } from '@mui/material/styles';
import AutoApplyrLogo from './AutoApplyrLogo';

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  variant?: 'permanent' | 'temporary';
}

const Sidebar: React.FC<SidebarProps> = ({ open, onClose, variant = 'permanent' }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { isDarkMode } = useCustomTheme();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('lg'));
  const [profileMenuOpen, setProfileMenuOpen] = React.useState(false);

  const navItems = [
    { path: '/', label: 'Dashboard', icon: <DashboardIcon /> },
    { path: '/resume', label: 'Resume', icon: <ResumeIcon /> },
    { path: '/search', label: 'Job Search', icon: <SearchIcon /> },
    { path: '/applications', label: 'Applications', icon: <ApplicationsIcon /> },
    { path: '/queue', label: 'Queue', icon: <QueueIcon /> },
    { path: '/settings', label: 'Settings', icon: <SettingsIcon /> },
  ];



  const handleNavigation = (path: string) => {
    navigate(path);
    if (isMobile) {
      onClose();
    }
  };

  const handleProfileMenuToggle = () => {
    setProfileMenuOpen(!profileMenuOpen);
  };

  const handleLogout = () => {
    logout();
    setProfileMenuOpen(false);
    if (isMobile) {
      onClose();
    }
  };

  const handleSettings = () => {
    navigate('/settings');
    setProfileMenuOpen(false);
    if (isMobile) {
      onClose();
    }
  };

  const sidebarContent = (
    <Box
      sx={{
        width: 280,
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: isDarkMode 
          ? 'rgba(15, 15, 35, 0.95)' 
          : 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(20px)',
        borderRight: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
        position: 'fixed',
        top: 0,
        left: 0,
        zIndex: theme.zIndex.drawer + 1,
      }}
    >
      {/* Header */}
      <Box sx={{ px: 3, py: 3, borderBottom: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}` }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2.5 }}>
            <AutoApplyrLogo size={32} isDarkMode={isDarkMode} />
            <Typography 
              variant="h6" 
              sx={{ 
                fontWeight: 900,
                fontSize: '1.25rem',
                fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
                letterSpacing: '-0.02em',
                color: isDarkMode ? '#ffffff' : '#1e293b',
                textShadow: isDarkMode 
                  ? '0 2px 4px rgba(0, 0, 0, 0.3)'
                  : '0 2px 4px rgba(0, 0, 0, 0.1)',
                transition: 'color 0.3s ease',
              }}
            >
              AutoApplyr
            </Typography>
          </Box>
          {isMobile && (
            <IconButton onClick={onClose} size="small">
              <CloseIcon />
            </IconButton>
          )}
        </Box>
      </Box>

      {/* Navigation */}
      <Box sx={{ flex: 1, p: 2 }}>
        <List sx={{ p: 0 }}>
          {navItems.map((item, index) => {
            const isActive = location.pathname === item.path;
            return (
              <ListItem key={item.path} sx={{ p: 0, mb: 1 }}>
                <Fade in={true} timeout={300 + index * 100}>
                  <ListItemButton
                    onClick={() => handleNavigation(item.path)}
                    sx={{
                      borderRadius: '12px',
                      py: 1.5,
                      px: 2,
                      backgroundColor: isActive 
                        ? (isDarkMode ? 'rgba(99, 102, 241, 0.2)' : 'rgba(99, 102, 241, 0.1)')
                        : 'transparent',
                      border: isActive 
                        ? `1px solid ${isDarkMode ? 'rgba(99, 102, 241, 0.3)' : 'rgba(99, 102, 241, 0.2)'}`
                        : '1px solid transparent',
                      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                      '&:hover': {
                        backgroundColor: isDarkMode 
                          ? 'rgba(255, 255, 255, 0.05)'
                          : 'rgba(0, 0, 0, 0.05)',
                        transform: 'translateX(4px)',
                      },
                    }}
                  >
                    <ListItemIcon 
                      sx={{ 
                        color: isActive ? 'primary.main' : 'text.secondary',
                        minWidth: 40,
                        transition: 'color 0.3s ease'
                      }}
                    >
                      {item.icon}
                    </ListItemIcon>
                    <ListItemText 
                      primary={item.label}
                      primaryTypographyProps={{
                        fontWeight: isActive ? 600 : 500,
                        color: isActive ? 'primary.main' : 'text.primary'
                      }}
                    />
                  </ListItemButton>
                </Fade>
              </ListItem>
            );
          })}
        </List>
      </Box>

      {/* Profile Section at Bottom */}
      <Box sx={{ p: 3, borderTop: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}` }}>
        <ListItemButton
          onClick={handleProfileMenuToggle}
          sx={{
            borderRadius: '12px',
            py: 1.5,
            px: 2,
            backgroundColor: profileMenuOpen 
              ? (isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.05)')
              : 'transparent',
            border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)'}`,
            '&:hover': {
              backgroundColor: isDarkMode 
                ? 'rgba(255, 255, 255, 0.08)'
                : 'rgba(0, 0, 0, 0.08)',
            },
          }}
        >
          <ListItemIcon sx={{ minWidth: 40 }}>
            <Avatar 
              sx={{ 
                width: 32, 
                height: 32, 
                bgcolor: 'primary.main',
                fontWeight: 600,
                fontSize: '0.875rem'
              }}
            >
              {user?.first_name?.[0]?.toUpperCase() || 'U'}
            </Avatar>
          </ListItemIcon>
          <ListItemText 
            primary={user?.first_name || 'User'}
            secondary={user?.email || 'user@example.com'}
            primaryTypographyProps={{
              fontWeight: 600,
              fontSize: '0.875rem'
            }}
            secondaryTypographyProps={{
              fontSize: '0.75rem',
              noWrap: true
            }}
          />
          <ExpandMoreIcon 
            sx={{ 
              transform: profileMenuOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.3s ease'
            }} 
          />
        </ListItemButton>

        <Collapse in={profileMenuOpen} timeout="auto" unmountOnExit>
          <Box sx={{ mt: 1 }}>
            <ListItemButton
              onClick={handleSettings}
              sx={{
                borderRadius: '8px',
                py: 1,
                px: 2,
                ml: 1,
                '&:hover': {
                  backgroundColor: isDarkMode 
                    ? 'rgba(255, 255, 255, 0.05)'
                    : 'rgba(0, 0, 0, 0.05)',
                },
              }}
            >
              <ListItemIcon sx={{ color: 'text.secondary', minWidth: 36 }}>
                <AccountIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText 
                primary="Profile Settings"
                primaryTypographyProps={{
                  fontWeight: 500,
                  fontSize: '0.875rem'
                }}
              />
            </ListItemButton>
            
            <ListItemButton
              onClick={handleLogout}
              sx={{
                borderRadius: '8px',
                py: 1,
                px: 2,
                ml: 1,
                '&:hover': {
                  backgroundColor: isDarkMode 
                    ? 'rgba(239, 68, 68, 0.1)'
                    : 'rgba(239, 68, 68, 0.05)',
                },
              }}
            >
              <ListItemIcon sx={{ color: '#ef4444', minWidth: 36 }}>
                <LogoutIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText 
                primary="Logout"
                primaryTypographyProps={{
                  fontWeight: 500,
                  color: '#ef4444',
                  fontSize: '0.875rem'
                }}
              />
            </ListItemButton>
          </Box>
        </Collapse>
      </Box>
    </Box>
  );

  if (variant === 'temporary') {
    return (
      <Drawer
        anchor="left"
        open={open}
        onClose={onClose}
        ModalProps={{
          keepMounted: true, // Better open performance on mobile
        }}
        PaperProps={{
          sx: {
            backgroundColor: 'transparent',
            boxShadow: 'none',
          }
        }}
      >
        {sidebarContent}
      </Drawer>
    );
  }

  return (
    <Box
      sx={{
        width: 280,
        flexShrink: 0,
        display: { xs: 'none', lg: 'block' },
      }}
    >
      {sidebarContent}
    </Box>
  );
};

export default Sidebar;