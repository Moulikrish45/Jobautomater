"""Celery tasks package for job application automation."""

from app.tasks.job_search_tasks import (
    search_jobs_for_user,
    calculate_match_scores_for_jobs,
    queue_jobs_for_application,
    continuous_job_search,
    cleanup_old_jobs,
    schedule_continuous_searches
)

from app.tasks.application_tasks import (
    apply_to_job_task,
    cleanup_stale_applications,
    retry_failed_applications
)

__all__ = [
    "search_jobs_for_user",
    "calculate_match_scores_for_jobs", 
    "queue_jobs_for_application",
    "continuous_job_search",
    "cleanup_old_jobs",
    "schedule_continuous_searches",
    "apply_to_job_task",
    "cleanup_stale_applications",
    "retry_failed_applications"
]