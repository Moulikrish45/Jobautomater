import React from 'react';
import { Box, CircularProgress } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';
import Auth from '../pages/Auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
      >
        <CircularProgress />
      </Box>
    );
  }

  if (!isAuthenticated) {
    return <Auth />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;