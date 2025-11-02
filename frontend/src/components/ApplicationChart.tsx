import React from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format, parseISO } from 'date-fns';
import { ApplicationTrend } from '../types/api';

interface ApplicationChartProps {
  data: ApplicationTrend[];
}

const ApplicationChart: React.FC<ApplicationChartProps> = ({ data }) => {
  // Format data for the chart
  const chartData = data.map(item => ({
    ...item,
    date: format(parseISO(item.date), 'MMM dd'),
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis 
          dataKey="date" 
          tick={{ fontSize: 12 }}
        />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip 
          labelFormatter={(label) => `Date: ${label}`}
          formatter={(value, name) => [value, typeof name === 'string' ? name.replace('_', ' ') : name]}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="applications_count"
          stroke="#1976d2"
          strokeWidth={2}
          name="Applications"
        />
        <Line
          type="monotone"
          dataKey="success_count"
          stroke="#2e7d32"
          strokeWidth={2}
          name="Successful"
        />
        <Line
          type="monotone"
          dataKey="response_count"
          stroke="#ed6c02"
          strokeWidth={2}
          name="Responses"
        />
      </LineChart>
    </ResponsiveContainer>
  );
};

export default ApplicationChart;