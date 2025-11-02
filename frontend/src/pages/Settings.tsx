import React, { useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Switch,
  FormControlLabel,
  Button,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Divider,
  Alert,
  Chip,
} from '@mui/material';
import {
  Save as SaveIcon,
  Refresh as RefreshIcon,
  Pause as PauseIcon,
  PlayArrow as PlayIcon,
} from '@mui/icons-material';

const Settings: React.FC = () => {
  const [automationEnabled, setAutomationEnabled] = useState(true);
  const [searchInterval, setSearchInterval] = useState(60); // minutes
  const [maxApplicationsPerDay, setMaxApplicationsPerDay] = useState(10);
  const [enabledPortals, setEnabledPortals] = useState(['linkedin', 'indeed', 'naukri']);
  const [minMatchScore, setMinMatchScore] = useState(0.7);
  const [notifications, setNotifications] = useState({
    email: true,
    browser: false,
    errors: true,
    success: false,
  });

  const handleSaveSettings = () => {
    // TODO: Implement settings save
    console.log('Saving settings...');
  };

  const handleToggleAutomation = () => {
    setAutomationEnabled(!automationEnabled);
    // TODO: Implement automation toggle API call
  };

  const portals = [
    { value: 'linkedin', label: 'LinkedIn' },
    { value: 'indeed', label: 'Indeed' },
    { value: 'naukri', label: 'Naukri' },
  ];

  return (
    <Box>
      <Typography variant="h4" component="h1" gutterBottom>
        Settings
      </Typography>

      <Grid container spacing={3}>
        {/* Automation Control */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="h6">Automation Control</Typography>
                <Button
                  variant={automationEnabled ? 'outlined' : 'contained'}
                  color={automationEnabled ? 'error' : 'success'}
                  startIcon={automationEnabled ? <PauseIcon /> : <PlayIcon />}
                  onClick={handleToggleAutomation}
                >
                  {automationEnabled ? 'Pause Automation' : 'Start Automation'}
                </Button>
              </Box>
              
              <Alert severity={automationEnabled ? 'success' : 'warning'} sx={{ mb: 2 }}>
                Automation is currently {automationEnabled ? 'active' : 'paused'}.
                {automationEnabled 
                  ? ' The system will continue searching and applying to jobs automatically.'
                  : ' No new applications will be submitted until you resume automation.'
                }
              </Alert>

              <FormControlLabel
                control={
                  <Switch
                    checked={automationEnabled}
                    onChange={(e) => setAutomationEnabled(e.target.checked)}
                  />
                }
                label="Enable automatic job applications"
              />
            </CardContent>
          </Card>
        </Grid>

        {/* Job Search Settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Job Search Settings
              </Typography>

              <TextField
                fullWidth
                margin="normal"
                label="Search Interval (minutes)"
                type="number"
                value={searchInterval}
                onChange={(e) => setSearchInterval(Number(e.target.value))}
                helperText="How often to search for new jobs"
              />

              <TextField
                fullWidth
                margin="normal"
                label="Max Applications Per Day"
                type="number"
                value={maxApplicationsPerDay}
                onChange={(e) => setMaxApplicationsPerDay(Number(e.target.value))}
                helperText="Daily limit for automatic applications"
              />

              <TextField
                fullWidth
                margin="normal"
                label="Minimum Match Score"
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.1 }}
                value={minMatchScore}
                onChange={(e) => setMinMatchScore(Number(e.target.value))}
                helperText="Only apply to jobs above this match score (0-1)"
              />

              <FormControl fullWidth margin="normal">
                <InputLabel>Enabled Job Portals</InputLabel>
                <Select
                  multiple
                  value={enabledPortals}
                  onChange={(e) => setEnabledPortals(e.target.value as string[])}
                  renderValue={(selected) => (
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                      {selected.map((value) => (
                        <Chip key={value} label={value} size="small" />
                      ))}
                    </Box>
                  )}
                >
                  {portals.map((portal) => (
                    <MenuItem key={portal.value} value={portal.value}>
                      {portal.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </CardContent>
          </Card>
        </Grid>

        {/* Notification Settings */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Notification Settings
              </Typography>

              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.email}
                    onChange={(e) => setNotifications({
                      ...notifications,
                      email: e.target.checked
                    })}
                  />
                }
                label="Email notifications"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.browser}
                    onChange={(e) => setNotifications({
                      ...notifications,
                      browser: e.target.checked
                    })}
                  />
                }
                label="Browser notifications"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.errors}
                    onChange={(e) => setNotifications({
                      ...notifications,
                      errors: e.target.checked
                    })}
                  />
                }
                label="Error notifications"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={notifications.success}
                    onChange={(e) => setNotifications({
                      ...notifications,
                      success: e.target.checked
                    })}
                  />
                }
                label="Success notifications"
              />
            </CardContent>
          </Card>
        </Grid>

        {/* System Status */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                System Status
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">
                      ✓
                    </Typography>
                    <Typography variant="body2">Database</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">
                      ✓
                    </Typography>
                    <Typography variant="body2">Job Search Agent</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">
                      ✓
                    </Typography>
                    <Typography variant="body2">Resume Builder</Typography>
                  </Box>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Box textAlign="center">
                    <Typography variant="h4" color="success.main">
                      ✓
                    </Typography>
                    <Typography variant="body2">Application Agent</Typography>
                  </Box>
                </Grid>
              </Grid>

              <Divider sx={{ my: 2 }} />

              <Box display="flex" gap={2}>
                <Button
                  variant="contained"
                  startIcon={<SaveIcon />}
                  onClick={handleSaveSettings}
                >
                  Save Settings
                </Button>
                <Button
                  variant="outlined"
                  startIcon={<RefreshIcon />}
                  onClick={() => window.location.reload()}
                >
                  Refresh Status
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default Settings;