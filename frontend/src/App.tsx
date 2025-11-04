import React, { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box, useMediaQuery } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Navbar from './components/Navbar';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Applications from './pages/Applications';
import JobQueue from './pages/JobQueue';
import Settings from './pages/Settings';
import JobSearch from './pages/JobSearch';
import ResumeUpload from './pages/ResumeUpload';
import { NotificationProvider } from './contexts/NotificationContext';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeContextProvider } from './contexts/ThemeContext';
import ProtectedRoute from './components/ProtectedRoute';

function AppContent() {
  const { user } = useAuth();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('lg'));
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleSidebarToggle = () => {
    setSidebarOpen(!sidebarOpen);
  };

  return (
    <NotificationProvider userId={user?.id || ''}>
      <Box 
        sx={{ 
          display: 'flex', 
          height: '100vh',
          background: theme.palette.mode === 'dark' 
            ? '#0f0f23'
            : '#f8fafc',
          position: 'relative',
          overflow: 'hidden',
          '&::before': {
            content: '""',
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: theme.palette.mode === 'dark'
              ? 'radial-gradient(circle at 20% 50%, rgba(120, 119, 198, 0.3), transparent), radial-gradient(circle at 80% 20%, rgba(255, 255, 255, 0.1), transparent)'
              : 'radial-gradient(circle at 20% 50%, rgba(99, 102, 241, 0.1), transparent), radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.1), transparent)',
            pointerEvents: 'none',
          }
        }}
      >
        {/* Sidebar */}
        <Sidebar 
          open={sidebarOpen} 
          onClose={handleSidebarToggle}
          variant={isMobile ? 'temporary' : 'permanent'}
        />

        {/* Main Content */}
        <Box 
          sx={{ 
            display: 'flex', 
            flexDirection: 'column', 
            flexGrow: 1, 
            position: 'relative', 
            zIndex: 1,
            height: '100vh',
            marginLeft: { xs: 0 },
            width: { xs: '100%', lg: 'calc(100% - 280px)' },
            filter: isMobile && sidebarOpen ? 'blur(4px)' : 'none',
            transition: 'filter 0.3s ease-in-out, margin-left 0.3s ease-in-out',
            pointerEvents: isMobile && sidebarOpen ? 'none' : 'auto',
          }}
        >
          <Navbar onMenuClick={handleSidebarToggle} />
          
          <Box 
            component="main" 
            sx={{ 
              flexGrow: 1,
              overflow: 'auto',
              height: 'calc(100vh - 64px)', // Subtract navbar height
              px: 0, // Remove default padding
            }}
          >
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/resume" element={<ResumeUpload />} />
              <Route path="/search" element={<JobSearch />} />
              <Route path="/applications" element={
                <Box sx={{ p: 3 }}>
                  <Applications />
                </Box>
              } />
              <Route path="/queue" element={
                <Box sx={{ p: 3 }}>
                  <JobQueue />
                </Box>
              } />
              <Route path="/settings" element={
                <Box sx={{ p: 3 }}>
                  <Settings />
                </Box>
              } />
            </Routes>
          </Box>
        </Box>
      </Box>
    </NotificationProvider>
  );
}

function App() {
  return (
    <ThemeContextProvider>
      <AuthProvider>
        <ProtectedRoute>
          <AppContent />
        </ProtectedRoute>
      </AuthProvider>
    </ThemeContextProvider>
  );
}

export default App;