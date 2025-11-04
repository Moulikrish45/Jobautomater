import axios from 'axios';
import {
  ApplicationSummary,
  ApplicationDetail,
  DashboardMetrics,
  ApplicationTrend,
  JobQueueItem,
  ApplicationStatus,
  ApplicationOutcome,
  JobPortal,
} from '../types/api';

const API_BASE_URL = '/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

// Request interceptor to add auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // If token is expired, try to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const token = localStorage.getItem('auth_token');
        if (token) {
          const refreshResponse = await axios.post(
            `${API_BASE_URL}/auth/refresh`,
            {},
            {
              headers: { Authorization: `Bearer ${token}` }
            }
          );

          const newToken = refreshResponse.data.access_token;
          localStorage.setItem('auth_token', newToken);
          localStorage.setItem('auth_user', JSON.stringify(refreshResponse.data.user));

          // Retry original request with new token
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          return api(originalRequest);
        }
      } catch (refreshError) {
        // Refresh failed, redirect to login
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
        window.location.href = '/';
        return Promise.reject(refreshError);
      }
    }

    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

export interface ApplicationFilters {
  status?: ApplicationStatus[];
  outcome?: ApplicationOutcome[];
  portal?: JobPortal[];
  date_from?: string;
  date_to?: string;
  company?: string;
  job_title?: string;
  min_match_score?: number;
  limit?: number;
  skip?: number;
}

export class DashboardAPI {
  // Applications
  static async getApplications(
    userId: string,
    filters?: ApplicationFilters
  ): Promise<ApplicationSummary[]> {
    const params = new URLSearchParams();
    
    if (filters) {
      if (filters.status) {
        filters.status.forEach(s => params.append('status', s));
      }
      if (filters.outcome) {
        filters.outcome.forEach(o => params.append('outcome', o));
      }
      if (filters.portal) {
        filters.portal.forEach(p => params.append('portal', p));
      }
      if (filters.date_from) params.append('date_from', filters.date_from);
      if (filters.date_to) params.append('date_to', filters.date_to);
      if (filters.company) params.append('company', filters.company);
      if (filters.job_title) params.append('job_title', filters.job_title);
      if (filters.min_match_score !== undefined) {
        params.append('min_match_score', filters.min_match_score.toString());
      }
      if (filters.limit) params.append('limit', filters.limit.toString());
      if (filters.skip) params.append('skip', filters.skip.toString());
    }

    const response = await api.get(
      `/dashboard/users/${userId}/applications?${params.toString()}`
    );
    return response.data;
  }

  static async getApplicationDetail(
    userId: string,
    applicationId: string
  ): Promise<ApplicationDetail> {
    const response = await api.get(
      `/dashboard/users/${userId}/applications/${applicationId}`
    );
    return response.data;
  }

  static async updateApplicationOutcome(
    userId: string,
    applicationId: string,
    outcome: ApplicationOutcome,
    notes?: string
  ): Promise<void> {
    await api.put(
      `/dashboard/users/${userId}/applications/${applicationId}/outcome`,
      { outcome, notes }
    );
  }

  static async updateApplicationTags(
    userId: string,
    applicationId: string,
    tags: string[]
  ): Promise<void> {
    await api.put(
      `/dashboard/users/${userId}/applications/${applicationId}/tags`,
      { tags }
    );
  }

  // Metrics and Analytics
  static async getDashboardMetrics(
    userId: string,
    days: number = 30
  ): Promise<DashboardMetrics> {
    const response = await api.get(
      `/dashboard/users/${userId}/metrics?days=${days}`
    );
    return response.data;
  }

  static async getApplicationTrends(
    userId: string,
    days: number = 30
  ): Promise<ApplicationTrend[]> {
    const response = await api.get(
      `/dashboard/users/${userId}/trends?days=${days}`
    );
    return response.data;
  }

  // Job Queue
  static async getJobQueue(
    userId: string,
    limit: number = 20,
    skip: number = 0
  ): Promise<JobQueueItem[]> {
    const response = await api.get(
      `/dashboard/users/${userId}/jobs/queue?limit=${limit}&skip=${skip}`
    );
    return response.data;
  }

  static async skipJob(
    userId: string,
    jobId: string,
    reason?: string
  ): Promise<void> {
    await api.post(
      `/dashboard/users/${userId}/jobs/${jobId}/skip`,
      { reason }
    );
  }
}

export default DashboardAPI;