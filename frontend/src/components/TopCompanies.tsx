import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemText,
  LinearProgress,
  Box,
  Chip,
} from '@mui/material';
import { CompanyMetric } from '../types/api';

interface TopCompaniesProps {
  companies: CompanyMetric[];
}

const TopCompanies: React.FC<TopCompaniesProps> = ({ companies }) => {
  const maxApplications = Math.max(...companies.map(c => c.applications), 1);

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Top Companies
        </Typography>
        {companies.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            No company data available
          </Typography>
        ) : (
          <List>
            {companies.map((company, index) => (
              <ListItem key={index} divider={index < companies.length - 1}>
                <ListItemText
                  primary={
                    <Box display="flex" justifyContent="space-between" alignItems="center">
                      <Typography variant="subtitle2">
                        {company.name}
                      </Typography>
                      <Chip
                        label={`${company.applications} apps`}
                        size="small"
                        variant="outlined"
                      />
                    </Box>
                  }
                  secondary={
                    <Box mt={1}>
                      <Box display="flex" justifyContent="space-between" mb={0.5}>
                        <Typography variant="caption" color="text.secondary">
                          Match Score: {company.avg_match_score}%
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {Math.round((company.applications / maxApplications) * 100)}%
                        </Typography>
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={(company.applications / maxApplications) * 100}
                        sx={{ height: 4, borderRadius: 2 }}
                      />
                    </Box>
                  }
                />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default TopCompanies;