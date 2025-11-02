import React, { useState } from 'react';
import {
  Box, TextField, Button, Card, CardContent, Typography, Grid,
  CircularProgress, Chip, Link, Alert, Paper, Stack, Divider,
  Container, Avatar, IconButton, Tooltip, Collapse, FormControl,
  InputLabel, Select, MenuItem, FormControlLabel, Switch
} from '@mui/material';
import {
  Search as SearchIcon,
  Business as BusinessIcon,
  LocationOn as LocationIcon,
  CalendarToday as CalendarIcon,
  OpenInNew as OpenIcon,
  Bookmark as BookmarkIcon,
  BookmarkBorder as BookmarkBorderIcon,
  FilterList as FilterIcon,
  ExpandMore as ExpandIcon,
  ExpandLess as CollapseIcon
} from '@mui/icons-material';

interface Job {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  description: string;
  posted: string;
  source: string;
  ats_score?: number;
  ats_recommendation?: string;
  matched_keywords?: string[];
  missing_keywords?: string[];
}

const JobSearch: React.FC = () => {
  const [keywords, setKeywords] = useState('');
  const [location, setLocation] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  
  // Advanced filters
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [datePosted, setDatePosted] = useState('all');
  const [jobType, setJobType] = useState('all');
  const [experience, setExperience] = useState('all');
  const [sortBy, setSortBy] = useState('relevance');

  const handleSearch = async () => {
    if (!keywords.trim()) return;
    
    setLoading(true);
    setError('');
    
    try {
      // Try resume-matched search first
      const userId = 'user123'; // TODO: Get from auth
      let res = await fetch(`/api/v1/jobs/match-resume?user_id=${userId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keywords: keywords.split(',').map(k => k.trim()),
          location: location.trim(),
          remote_only: remoteOnly,
          date_posted: datePosted,
          job_type: jobType,
          experience: experience,
          sort_by: sortBy
        })
      });
      
      // Fallback to regular search if no resume
      if (res.status === 400) {
        res = await fetch('/api/v1/jobs/search/free', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            keywords: keywords.split(',').map(k => k.trim()),
            location: location.trim(),
            remote_only: remoteOnly,
            date_posted: datePosted,
            job_type: jobType,
            experience: experience,
            sort_by: sortBy
          })
        });
      }
      
      const data = await res.json();
      if (data.success) {
        setJobs(data.jobs);
      } else {
        setError('Search failed');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Container maxWidth="lg">
      <Box sx={{ py: 4 }}>
        {/* Header */}
        <Box sx={{ mb: 4, textAlign: 'center' }}>
          <Typography variant="h3" fontWeight="bold" gutterBottom>
            Find Your Dream Job
          </Typography>
          <Typography variant="subtitle1" color="text.secondary">
            Search across multiple job boards instantly
          </Typography>
        </Box>

        {/* Search Bar */}
        <Paper elevation={3} sx={{ p: 3, mb: 4, borderRadius: 3 }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={4}>
              <TextField
                fullWidth
                label="What job are you looking for?"
                placeholder="e.g. Python Developer, Data Scientist"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                variant="outlined"
                InputProps={{
                  startAdornment: <SearchIcon sx={{ mr: 1, color: 'text.secondary' }} />
                }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField
                fullWidth
                label="Location"
                placeholder="Remote, USA, Europe"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                variant="outlined"
                InputProps={{
                  startAdornment: <LocationIcon sx={{ mr: 1, color: 'text.secondary' }} />
                }}
              />
            </Grid>
            <Grid item xs={12} md={2}>
              <Button
                fullWidth
                variant="outlined"
                size="large"
                startIcon={showFilters ? <CollapseIcon /> : <ExpandIcon />}
                onClick={() => setShowFilters(!showFilters)}
                sx={{ height: '56px', borderRadius: 2 }}
              >
                Filters
              </Button>
            </Grid>
            <Grid item xs={12} md={3}>
              <Button
                fullWidth
                variant="contained"
                size="large"
                startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <SearchIcon />}
                onClick={handleSearch}
                disabled={loading}
                sx={{ height: '56px', borderRadius: 2 }}
              >
                {loading ? 'Searching...' : 'Search Jobs'}
              </Button>
            </Grid>
          </Grid>

          {/* Advanced Filters */}
          <Collapse in={showFilters}>
            <Divider sx={{ my: 3 }} />
            <Grid container spacing={2}>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth>
                  <InputLabel>Date Posted</InputLabel>
                  <Select value={datePosted} onChange={(e) => setDatePosted(e.target.value)} label="Date Posted">
                    <MenuItem value="all">Any Time</MenuItem>
                    <MenuItem value="today">Today</MenuItem>
                    <MenuItem value="week">Past Week</MenuItem>
                    <MenuItem value="month">Past Month</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth>
                  <InputLabel>Job Type</InputLabel>
                  <Select value={jobType} onChange={(e) => setJobType(e.target.value)} label="Job Type">
                    <MenuItem value="all">All Types</MenuItem>
                    <MenuItem value="fulltime">Full-time</MenuItem>
                    <MenuItem value="parttime">Part-time</MenuItem>
                    <MenuItem value="contract">Contract</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth>
                  <InputLabel>Experience</InputLabel>
                  <Select value={experience} onChange={(e) => setExperience(e.target.value)} label="Experience">
                    <MenuItem value="all">All Levels</MenuItem>
                    <MenuItem value="entry">Entry Level</MenuItem>
                    <MenuItem value="mid">Mid Level</MenuItem>
                    <MenuItem value="senior">Senior Level</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth>
                  <InputLabel>Sort By</InputLabel>
                  <Select value={sortBy} onChange={(e) => setSortBy(e.target.value)} label="Sort By">
                    <MenuItem value="relevance">Relevance</MenuItem>
                    <MenuItem value="date">Date Posted</MenuItem>
                    <MenuItem value="company">Company Name</MenuItem>
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12}>
                <FormControlLabel
                  control={<Switch checked={remoteOnly} onChange={(e) => setRemoteOnly(e.target.checked)} />}
                  label="Remote Jobs Only"
                />
              </Grid>
            </Grid>
          </Collapse>
        </Paper>

        {error && <Alert severity="error" sx={{ mb: 3, borderRadius: 2 }}>{error}</Alert>}

        {/* Results Header */}
        {jobs.length > 0 && (
          <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 2 }}>
            <Typography variant="h5" fontWeight="600">
              {jobs.length} Jobs Found
            </Typography>
            <Stack direction="row" spacing={1}>
              <Chip label="8 Sources" color="primary" size="small" />
              <Chip label="LinkedIn" size="small" variant="outlined" />
              <Chip label="Indeed" size="small" variant="outlined" />
              <Chip label="Glassdoor" size="small" variant="outlined" />
              <Chip label="+5 More" size="small" variant="outlined" />
            </Stack>
          </Box>
        )}

        {/* Job Cards */}
        <Stack spacing={2}>
          {jobs.map((job) => (
            <Card
              key={job.id}
              elevation={2}
              sx={{
                borderRadius: 3,
                transition: 'all 0.3s',
                '&:hover': {
                  elevation: 6,
                  transform: 'translateY(-4px)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.12)'
                }
              }}
            >
              <CardContent sx={{ p: 3 }}>
                <Grid container spacing={2}>
                  {/* Company Logo */}
                  <Grid item xs="auto">
                    <Avatar
                      sx={{
                        width: 64,
                        height: 64,
                        bgcolor: 'primary.main',
                        fontSize: '1.5rem'
                      }}
                    >
                      {job.company.charAt(0).toUpperCase()}
                    </Avatar>
                  </Grid>

                  {/* Job Details */}
                  <Grid item xs>
                    <Box display="flex" justifyContent="space-between" alignItems="start">
                      <Box flex={1}>
                        <Typography variant="h6" fontWeight="600" gutterBottom>
                          {job.title}
                        </Typography>
                        
                        <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
                          <Box display="flex" alignItems="center" gap={0.5}>
                            <BusinessIcon fontSize="small" color="action" />
                            <Typography variant="body2" color="text.secondary">
                              {job.company}
                            </Typography>
                          </Box>
                          <Box display="flex" alignItems="center" gap={0.5}>
                            <LocationIcon fontSize="small" color="action" />
                            <Typography variant="body2" color="text.secondary">
                              {job.location}
                            </Typography>
                          </Box>
                          <Box display="flex" alignItems="center" gap={0.5}>
                            <CalendarIcon fontSize="small" color="action" />
                            <Typography variant="body2" color="text.secondary">
                              {new Date(job.posted).toLocaleDateString()}
                            </Typography>
                          </Box>
                        </Stack>

                        <Typography
                          variant="body2"
                          color="text.secondary"
                          sx={{
                            mb: 2,
                            display: '-webkit-box',
                            WebkitLineClamp: 3,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden'
                          }}
                        >
                          {job.description}
                        </Typography>

                        <Box display="flex" gap={1} flexWrap="wrap">
                          <Chip
                            label={job.source}
                            size="small"
                            color="primary"
                            variant="outlined"
                          />
                          {job.location.toLowerCase().includes('remote') && (
                            <Chip label="Remote" size="small" color="success" />
                          )}
                          {job.ats_score !== undefined && (
                            <Chip
                              label={`ATS: ${job.ats_score}%`}
                              size="small"
                              color={job.ats_score >= 70 ? 'success' : job.ats_score >= 50 ? 'warning' : 'error'}
                            />
                          )}
                        </Box>
                      </Box>

                      {/* Action Buttons */}
                      <Stack direction="row" spacing={1}>
                        <Tooltip title="Save for later">
                          <IconButton size="small">
                            <BookmarkBorderIcon />
                          </IconButton>
                        </Tooltip>
                        <Button
                          variant="contained"
                          endIcon={<OpenIcon />}
                          href={job.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          sx={{ borderRadius: 2 }}
                        >
                          Apply Now
                        </Button>
                      </Stack>
                    </Box>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          ))}
        </Stack>

        {/* Empty State */}
        {!loading && jobs.length === 0 && keywords && (
          <Paper
            elevation={0}
            sx={{
              p: 6,
              textAlign: 'center',
              bgcolor: 'grey.50',
              borderRadius: 3
            }}
          >
            <SearchIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
            <Typography variant="h6" gutterBottom>
              No jobs found
            </Typography>
            <Typography color="text.secondary">
              Try different keywords or location
            </Typography>
          </Paper>
        )}
      </Box>
    </Container>
  );
};

export default JobSearch;
