import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { Box } from '@mui/material';
import Navbar from './components/Navbar';
import Dashboard from './pages/Dashboard';
import Applications from './pages/Applications';
import JobQueue from './pages/JobQueue';
import Settings from './pages/Settings';
import JobSearch from './pages/JobSearch';
import ResumeUpload from './pages/ResumeUpload';
import { NotificationProvider } from './contexts/NotificationContext';

function App() {
  // TODO: Get user ID from authentication context
  const userId = 'user123';

  return (
    <NotificationProvider userId={userId}>
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', bgcolor: '#f5f5f5' }}>
        <Navbar />
        <Box component="main" sx={{ flexGrow: 1 }}>
          <Routes>
            <Route path="/" element={<Box sx={{ p: 3 }}><Dashboard /></Box>} />
            <Route path="/resume" element={<ResumeUpload />} />
            <Route path="/search" element={<JobSearch />} />
            <Route path="/applications" element={<Box sx={{ p: 3 }}><Applications /></Box>} />
            <Route path="/queue" element={<Box sx={{ p: 3 }}><JobQueue /></Box>} />
            <Route path="/settings" element={<Box sx={{ p: 3 }}><Settings /></Box>} />
          </Routes>
        </Box>
      </Box>
    </NotificationProvider>
  );
}

export default App;