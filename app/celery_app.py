"""Celery application configuration for background task processing."""

from celery import Celery
from app.config import settings

# Create Celery instance
celery_app = Celery(
    "job_automation",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks"]  # Will be created in later tasks
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Task routing (will be expanded in later tasks)
celery_app.conf.task_routes = {
    "app.tasks.job_search.*": {"queue": "job_search"},
    "app.tasks.resume_builder.*": {"queue": "resume_builder"},
    "app.tasks.application.*": {"queue": "application"},
}