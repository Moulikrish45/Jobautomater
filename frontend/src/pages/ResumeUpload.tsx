import React, { useState } from 'react';
import {
  Box, Button, Card, CardContent, Typography, Container, Alert,
  LinearProgress, Chip, Stack, Paper, Grid, Divider, Fade
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  CheckCircle as CheckIcon,
  Description as FileIcon
} from '@mui/icons-material';
import { useTheme as useCustomTheme } from '../contexts/ThemeContext';

const ResumeUpload: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState(false);
  const [resumeData, setResumeData] = useState<any>(null);
  const [matchedJobs, setMatchedJobs] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const { isDarkMode } = useCustomTheme();

  const userId = 'user123'; // TODO: Get from auth

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`/api/v1/jobs/upload-resume?user_id=${userId}`, {
        method: 'POST',
        body: formData
      });

      const data = await res.json();
      if (data.success) {
        setResumeData(data.resume_data);
        setMatchedJobs(data.matched_jobs || []);
        setUploaded(true);
      } else {
        setError('Upload failed');
      }
    } catch (err) {
      setError('Network error');
    } finally {
      setUploading(false);
    }
  };

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Fade in={true} timeout={800}>
        <Box>
          <Typography 
            variant="h4" 
            fontWeight="bold" 
            gutterBottom 
            textAlign="center"
            sx={{ 
              color: isDarkMode ? '#ffffff' : '#1e293b',
              transition: 'color 0.3s ease',
            }}
          >
            Upload Your Resume
          </Typography>
          <Typography variant="subtitle1" color="text.secondary" textAlign="center" sx={{ mb: 4 }}>
            We'll analyze your resume and match you with the best jobs
          </Typography>

          {!uploaded ? (
            <Card 
              sx={{ 
                borderRadius: '20px',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: isDarkMode 
                    ? '0 12px 40px rgba(0, 0, 0, 0.4)'
                    : '0 12px 40px rgba(0, 0, 0, 0.15)',
                }
              }}
            >
              <CardContent sx={{ p: 4 }}>
                <Box
                  sx={{
                    border: '2px dashed',
                    borderColor: file ? 'primary.main' : (isDarkMode ? 'rgba(255, 255, 255, 0.3)' : 'grey.300'),
                    borderRadius: 2,
                    p: 4,
                    textAlign: 'center',
                    bgcolor: file 
                      ? (isDarkMode ? 'rgba(99, 102, 241, 0.1)' : 'primary.50')
                      : (isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'grey.50'),
                    cursor: 'pointer',
                    transition: 'all 0.3s',
                    '&:hover': {
                      borderColor: 'primary.main',
                      bgcolor: isDarkMode ? 'rgba(99, 102, 241, 0.1)' : 'primary.50'
                    }
                  }}
                  onClick={() => document.getElementById('file-input')?.click()}
                >
                <input
                  id="file-input"
                  type="file"
                  accept=".pdf,.doc,.docx,.txt"
                  onChange={handleFileChange}
                  style={{ display: 'none' }}
                />
                
                {file ? (
                  <>
                    <FileIcon sx={{ fontSize: 64, color: 'primary.main', mb: 2 }} />
                    <Typography variant="h6">{file.name}</Typography>
                    <Typography variant="body2" color="text.secondary">
                      {(file.size / 1024).toFixed(2)} KB
                    </Typography>
                  </>
                ) : (
                  <>
                    <UploadIcon sx={{ fontSize: 64, color: 'text.secondary', mb: 2 }} />
                    <Typography variant="h6" gutterBottom color="text.primary">
                      Click to upload or drag and drop
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      PDF, DOC, DOCX, or TXT (Max 5MB)
                    </Typography>
                  </>
                )}
              </Box>

              {error && (
                <Alert 
                  severity="error" 
                  sx={{ 
                    mt: 2,
                    backgroundColor: isDarkMode 
                      ? 'rgba(244, 67, 54, 0.1)'
                      : 'rgba(244, 67, 54, 0.05)',
                    border: `1px solid rgba(244, 67, 54, ${isDarkMode ? '0.3' : '0.2'})`,
                    borderRadius: '12px',
                    color: 'text.primary',
                    '& .MuiAlert-icon': { color: '#f44336' }
                  }}
                >
                  {error}
                </Alert>
              )}

              {file && (
                <Button
                  fullWidth
                  variant="contained"
                  size="large"
                  startIcon={uploading ? null : <UploadIcon />}
                  onClick={handleUpload}
                  disabled={uploading}
                  sx={{ mt: 3, py: 1.5 }}
                >
                  {uploading ? 'Analyzing Resume...' : 'Upload & Analyze'}
                </Button>
              )}

              {uploading && <LinearProgress sx={{ mt: 2 }} />}
              </CardContent>
            </Card>
          ) : (
            <Card 
              sx={{ 
                borderRadius: '20px',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: isDarkMode 
                    ? '0 12px 40px rgba(0, 0, 0, 0.4)'
                    : '0 12px 40px rgba(0, 0, 0, 0.15)',
                }
              }}
            >
            <CardContent sx={{ p: 4 }}>
              <Box textAlign="center" sx={{ mb: 3 }}>
                <CheckIcon sx={{ fontSize: 64, color: 'success.main', mb: 2 }} />
                <Typography variant="h5" fontWeight="600" gutterBottom>
                  Resume Uploaded Successfully!
                </Typography>
                <Typography color="text.secondary">
                  We've analyzed your resume and extracted key information
                </Typography>
              </Box>

              <Divider sx={{ my: 3 }} />

              <Grid container spacing={3}>
                <Grid item xs={12} md={6}>
                  <Paper 
                    elevation={0} 
                    sx={{ 
                      p: 2, 
                      bgcolor: isDarkMode ? 'rgba(99, 102, 241, 0.1)' : 'primary.50', 
                      borderRadius: 2,
                      border: `1px solid ${isDarkMode ? 'rgba(99, 102, 241, 0.3)' : 'transparent'}`
                    }}
                  >
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Skills Found
                    </Typography>
                    <Typography variant="h4" fontWeight="bold" color="primary">
                      {resumeData?.skills?.length || 0}
                    </Typography>
                  </Paper>
                </Grid>
                <Grid item xs={12} md={6}>
                  <Paper 
                    elevation={0} 
                    sx={{ 
                      p: 2, 
                      bgcolor: isDarkMode ? 'rgba(16, 185, 129, 0.1)' : 'success.50', 
                      borderRadius: 2,
                      border: `1px solid ${isDarkMode ? 'rgba(16, 185, 129, 0.3)' : 'transparent'}`
                    }}
                  >
                    <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                      Experience Entries
                    </Typography>
                    <Typography variant="h4" fontWeight="bold" color="success.main">
                      {resumeData?.experience?.length || 0}
                    </Typography>
                  </Paper>
                </Grid>
              </Grid>

              {resumeData?.skills && resumeData.skills.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="subtitle1" fontWeight="600" gutterBottom>
                    Detected Skills
                  </Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {resumeData.skills.slice(0, 15).map((skill: string, i: number) => (
                      <Chip key={i} label={skill} color="primary" variant="outlined" />
                    ))}
                  </Stack>
                </Box>
              )}

              {matchedJobs.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Divider sx={{ mb: 2 }} />
                  <Typography variant="h6" fontWeight="600" gutterBottom>
                    🎯 Matched Jobs Found!
                  </Typography>
                  <Grid container spacing={2}>
                    <Grid item xs={4}>
                      <Paper 
                        elevation={0} 
                        sx={{ 
                          p: 2, 
                          bgcolor: isDarkMode ? 'rgba(16, 185, 129, 0.1)' : 'success.50', 
                          textAlign: 'center',
                          border: `1px solid ${isDarkMode ? 'rgba(16, 185, 129, 0.3)' : 'transparent'}`
                        }}
                      >
                        <Typography variant="h5" fontWeight="bold" color="success.main">
                          {matchedJobs.filter(j => j.ats_score >= 70).length}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">High Match</Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={4}>
                      <Paper 
                        elevation={0} 
                        sx={{ 
                          p: 2, 
                          bgcolor: isDarkMode ? 'rgba(245, 158, 11, 0.1)' : 'warning.50', 
                          textAlign: 'center',
                          border: `1px solid ${isDarkMode ? 'rgba(245, 158, 11, 0.3)' : 'transparent'}`
                        }}
                      >
                        <Typography variant="h5" fontWeight="bold" color="warning.main">
                          {matchedJobs.filter(j => j.ats_score >= 50 && j.ats_score < 70).length}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">Medium Match</Typography>
                      </Paper>
                    </Grid>
                    <Grid item xs={4}>
                      <Paper 
                        elevation={0} 
                        sx={{ 
                          p: 2, 
                          bgcolor: isDarkMode ? 'rgba(255, 255, 255, 0.05)' : 'grey.100', 
                          textAlign: 'center',
                          border: `1px solid ${isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'transparent'}`
                        }}
                      >
                        <Typography variant="h5" fontWeight="bold" color="text.primary">
                          {matchedJobs.length}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">Total Jobs</Typography>
                      </Paper>
                    </Grid>
                  </Grid>
                  
                  <Box sx={{ mt: 3 }}>
                    {matchedJobs.slice(0, 5).map((job, i) => (
                      <Card 
                        key={i} 
                        sx={{ 
                          mb: 2, 
                          borderRadius: '12px',
                          transition: 'all 0.3s ease',
                          '&:hover': { 
                            boxShadow: isDarkMode 
                              ? '0 8px 32px rgba(0, 0, 0, 0.4)'
                              : '0 8px 32px rgba(0, 0, 0, 0.15)',
                            transform: 'translateY(-2px)'
                          } 
                        }}
                      >
                        <CardContent>
                          <Stack direction="row" justifyContent="space-between" alignItems="start">
                            <Box>
                              <Typography variant="h6" fontWeight="600">{job.title}</Typography>
                              <Typography variant="body2" color="text.secondary">{job.company} • {job.location}</Typography>
                            </Box>
                            <Chip 
                              label={`${Math.round(job.ats_score)}%`} 
                              color={job.ats_score >= 70 ? 'success' : job.ats_score >= 40 ? 'warning' : 'default'}
                              size="small"
                            />
                          </Stack>
                          <Button 
                            size="small" 
                            href={job.url} 
                            target="_blank" 
                            sx={{ mt: 1 }}
                          >
                            View Job
                          </Button>
                        </CardContent>
                      </Card>
                    ))}
                  </Box>
                </Box>
              )}

              <Button
                fullWidth
                variant="contained"
                size="large"
                onClick={async () => {
                  setSearching(true);
                  setError('');
                  try {
                    const res = await fetch(`/api/v1/jobs/search-with-resume?user_id=${userId}`, {
                      method: 'POST'
                    });
                    const data = await res.json();
                    console.log('Search response:', data);
                    if (data.success) {
                      setMatchedJobs(data.matched_jobs || []);
                      console.log('Matched jobs:', data.matched_jobs?.length);
                    } else {
                      setError('Failed to search jobs');
                    }
                  } catch (err) {
                    console.error('Search error:', err);
                    setError('Failed to search jobs');
                  } finally {
                    setSearching(false);
                  }
                }}
                disabled={searching}
                sx={{ mt: 4, py: 1.5 }}
              >
                {searching ? 'Searching Jobs...' : 'Find Matching Jobs'}
              </Button>
              {searching && <LinearProgress sx={{ mt: 2 }} />}
              {error && (
                <Alert 
                  severity="error" 
                  sx={{ 
                    mt: 2,
                    backgroundColor: isDarkMode 
                      ? 'rgba(244, 67, 54, 0.1)'
                      : 'rgba(244, 67, 54, 0.05)',
                    border: `1px solid rgba(244, 67, 54, ${isDarkMode ? '0.3' : '0.2'})`,
                    borderRadius: '12px',
                    color: 'text.primary',
                    '& .MuiAlert-icon': { color: '#f44336' }
                  }}
                >
                  {error}
                </Alert>
              )}

              <Button
                fullWidth
                variant="outlined"
                size="large"
                onClick={() => {
                  setUploaded(false);
                  setFile(null);
                  setResumeData(null);
                }}
                sx={{ mt: 2 }}
              >
                Upload Another Resume
              </Button>
              </CardContent>
            </Card>
          )}
        </Box>
      </Fade>
    </Container>
  );
};

export default ResumeUpload;
