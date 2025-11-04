// API response types
export interface ApplicationSummary {
  id: string;
  job_title: string;
  company_name: string;
  portal: JobPortal;
  status: ApplicationStatus;
  outcome?: ApplicationOutcome;
  applied_at?: string;
  created_at: string;
  updated_at: string;
  total_attempts: number;
  match_score: number;
  job_location: JobLocation;
  company_logo?: string;
  salary?: SalaryInfo;
  is_archived: boolean;
  tags: string[];
}

export interface ApplicationDetail extends ApplicationSummary {
  user_id: string;
  job_id: string;
  job_url: string;
  attempts: ApplicationAttempt[];
  submission_data?: SubmissionData;
  notes?: string;
  job_details: JobDetails;
}

export interface ApplicationAttempt {
  attempt_number: number;
  started_at: string;
  completed_at?: string;
  success: boolean;
  error_message?: string;
  screenshots: string[];
  form_data_used?: Record<string, any>;
}

export interface SubmissionData {
  form_fields: Record<string, any>;
  resume_filename?: string;
  cover_letter?: string;
  additional_documents: string[];
  submission_id?: string;
  confirmation_number?: string;
}

export interface JobDetails {
  description: string;
  requirements: string[];
  responsibilities: string[];
  skills_required: string[];
  job_type?: string;
  experience_level?: string;
  salary?: SalaryInfo;
  location: JobLocation;
  company: CompanyInfo;
  posted_date?: string;
  match_score: number;
}

export interface SalaryInfo {
  min_salary?: number;
  max_salary?: number;
  currency: string;
  period: string;
}

export interface JobLocation {
  city?: string;
  state?: string;
  country: string;
  is_remote: boolean;
  is_hybrid: boolean;
}

export interface CompanyInfo {
  name: string;
  size?: string;
  industry?: string;
  website?: string;
  logo_url?: string;
}

export interface DashboardMetrics {
  total_applications: number;
  applications_by_status: Record<ApplicationStatus, number>;
  applications_by_outcome: Record<ApplicationOutcome, number>;
  applications_by_portal: Record<JobPortal, number>;
  success_rate: number;
  response_rate: number;
  average_response_time_days?: number;
  applications_last_30_days: number;
  interviews_scheduled: number;
  offers_received: number;
  top_companies: CompanyMetric[];
  recent_activity: ActivityItem[];
  monthly_trends: {
    month: string;
    applications: number;
    responses: number;
    interviews: number;
    offers: number;
  }[];
}

export interface CompanyMetric {
  name: string;
  applications: number;
  avg_match_score: number;
}

export interface ActivityItem {
  job_title: string;
  company: string;
  status: ApplicationStatus;
  outcome?: ApplicationOutcome;
  created_at: string;
  applied_at?: string;
}

export interface ApplicationTrend {
  date: string;
  applications_count: number;
  success_count: number;
  response_count: number;
  interview_count: number;
  offer_count: number;
}

export interface JobQueueItem {
  id: string;
  title: string;
  company: string;
  location: JobLocation;
  portal: JobPortal;
  match_score: number;
  discovered_at: string;
  url: string;
  description?: string;
  skills_required?: string[];
  job_type?: string;
  experience_level?: string;
}

// API Request/Response types
export interface ApiResponse<T> {
  data: T;
  message?: string;
  success: boolean;
  pagination?: {
    total: number;
    page: number;
    limit: number;
    total_pages: number;
  };
}

export interface ErrorResponse {
  error: string;
  message: string;
  statusCode: number;
  timestamp: string;
  path: string;
}

// Enums
export enum ApplicationStatus {
  PENDING = 'pending',
  IN_PROGRESS = 'in_progress',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum ApplicationOutcome {
  APPLIED = 'applied',
  VIEWED = 'viewed',
  REJECTED = 'rejected',
  INTERVIEW_SCHEDULED = 'interview_scheduled',
  INTERVIEW_COMPLETED = 'interview_completed',
  OFFER_RECEIVED = 'offer_received',
  OFFER_ACCEPTED = 'offer_accepted',
  OFFER_DECLINED = 'offer_declined',
}

export enum JobPortal {
  LINKEDIN = 'linkedin',
  INDEED = 'indeed',
  NAUKRI = 'naukri',
}