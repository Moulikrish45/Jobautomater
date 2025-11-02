"""Celery tasks for job search and matching operations."""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from celery import Task
from app.celery_app import celery_app
import asyncio
from app.mcp.scrapers.scraper_manager import scraper_manager
from app.services.job_matching_service import job_matching_service
from app.repositories.user_repository import UserRepository
from app.repositories.job_repository import JobRepository
from app.models.job import Job, JobPortal


logger = logging.getLogger("job_search_tasks")


class CallbackTask(Task):
    """Base task class with error handling and callbacks."""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Task {task_id} failed: {exc}")
        # Could send notifications here
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(f"Task {task_id} completed successfully")


@celery_app.task(bind=True, base=CallbackTask, name="search_jobs_for_user")
def search_jobs_for_user(
    self,
    user_id: str,
    keywords: Optional[List[str]] = None,
    location: Optional[str] = None,
    portals: Optional[List[str]] = None,
    max_pages_per_portal: int = 3
) -> Dict[str, Any]:
    """Search for jobs for a specific user.
    
    Args:
        user_id: User ID
        keywords: Search keywords (optional, will use user preferences)
        location: Job location (optional, will use user preferences)
        portals: List of portals to search (optional, defaults to all)
        max_pages_per_portal: Maximum pages to scrape per portal
        
    Returns:
        Dictionary containing search results
    """
    try:
        logger.info(f"Starting job search for user {user_id}")
        
        # Get user preferences if not provided
        user_repo = UserRepository()
        user = user_repo.get_by_id_sync(user_id)
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        preferences = user.profile.get('preferences', {})
        
        # Use provided parameters or fall back to user preferences
        search_keywords = keywords or preferences.get('desired_roles', [])
        search_location = location or preferences.get('locations', ['Remote'])[0]
        search_portals = portals or ['linkedin', 'indeed', 'naukri']
        
        if not search_keywords:
            raise ValueError("No search keywords provided or found in user preferences")
        
        # Perform the search (run async function in sync context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            search_results = loop.run_until_complete(
                scraper_manager.search_all_portals(
                    keywords=search_keywords,
                    location=search_location,
                    portals=search_portals,
                    max_pages_per_portal=max_pages_per_portal
                )
            )
        finally:
            loop.close()
        
        # Store jobs in database
        job_repo = JobRepository()
        stored_jobs = []
        
        for job_data in search_results.get('jobs', []):
            try:
                # Create job object
                job = Job(
                    external_id=job_data.get('external_id'),
                    title=job_data.get('title'),
                    company=job_data.get('company'),
                    location=job_data.get('location'),
                    description=job_data.get('description', ''),
                    requirements=job_data.get('requirements', []),
                    salary=job_data.get('salary'),
                    url=job_data.get('url'),
                    portal=job_data.get('portal'),
                    posted_date=datetime.utcnow(),  # Use current time as fallback
                    match_score=0.0,  # Will be calculated later
                    status='discovered',
                    user_id=user_id,
                    created_at=datetime.utcnow()
                )
                
                # Check if job already exists
                existing_job = job_repo.get_by_external_id_and_portal_sync(
                    job.external_id, job.portal
                )
                
                if not existing_job:
                    saved_job = job_repo.create_sync(job)
                    stored_jobs.append(saved_job)
                    logger.info(f"Stored new job: {job.title} at {job.company}")
                else:
                    logger.debug(f"Job already exists: {job.title} at {job.company}")
                
            except Exception as e:
                logger.warning(f"Failed to store job: {e}")
                continue
        
        # Calculate match scores for new jobs
        if stored_jobs:
            calculate_match_scores_for_jobs.delay(
                user_id, 
                [str(job.id) for job in stored_jobs]
            )
        
        result = {
            'user_id': user_id,
            'search_results': search_results,
            'jobs_stored': len(stored_jobs),
            'total_jobs_found': len(search_results.get('jobs', [])),
            'task_id': self.request.id,
            'completed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Job search completed for user {user_id}: {len(stored_jobs)} new jobs stored")
        return result
        
    except Exception as e:
        logger.error(f"Job search failed for user {user_id}: {e}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="calculate_match_scores_for_jobs")
def calculate_match_scores_for_jobs(self, user_id: str, job_ids: List[str]) -> Dict[str, Any]:
    """Calculate match scores for a list of jobs for a user.
    
    Args:
        user_id: User ID
        job_ids: List of job IDs
        
    Returns:
        Dictionary containing match calculation results
    """
    try:
        logger.info(f"Calculating match scores for {len(job_ids)} jobs for user {user_id}")
        
        # Calculate matches
        matches = job_matching_service.batch_calculate_matches_sync(user_id, job_ids)
        
        # Update job records with match scores
        job_repo = JobRepository()
        updated_jobs = 0
        
        for match in matches:
            try:
                job_id = match['job_id']
                match_score = match['overall_score']
                
                job = job_repo.get_by_id_sync(job_id)
                if job:
                    job.match_score = match_score
                    job_repo.update_sync(job_id, {'match_score': match_score})
                    updated_jobs += 1
                
            except Exception as e:
                logger.warning(f"Failed to update match score for job {job_id}: {e}")
                continue
        
        # Queue high-scoring jobs for application
        high_scoring_matches = [
            match for match in matches 
            if match['overall_score'] >= 0.7
        ]
        
        if high_scoring_matches:
            queue_jobs_for_application.delay(
                user_id,
                [match['job_id'] for match in high_scoring_matches[:10]]  # Limit to top 10
            )
        
        result = {
            'user_id': user_id,
            'job_ids_processed': job_ids,
            'matches_calculated': len(matches),
            'jobs_updated': updated_jobs,
            'high_scoring_jobs': len(high_scoring_matches),
            'task_id': self.request.id,
            'completed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Match calculation completed: {updated_jobs} jobs updated")
        return result
        
    except Exception as e:
        logger.error(f"Match calculation failed: {e}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="queue_jobs_for_application")
def queue_jobs_for_application(
    self, 
    user_id: str, 
    job_ids: List[str],
    priority: int = 5
) -> Dict[str, Any]:
    """Queue jobs for automated application.
    
    Args:
        user_id: User ID
        job_ids: List of job IDs to queue
        priority: Application priority (1-10)
        
    Returns:
        Dictionary containing queueing results
    """
    try:
        logger.info(f"Queueing {len(job_ids)} jobs for application for user {user_id}")
        
        job_repo = JobRepository()
        queued_jobs = 0
        
        for job_id in job_ids:
            try:
                job = job_repo.get_by_id_sync(job_id)
                if job and job.status == 'discovered':
                    # Update job status to queued
                    job_repo.update_sync(job_id, {
                        'status': 'queued',
                        'updated_at': datetime.utcnow()
                    })
                    
                    # Schedule application task (will be implemented in later tasks)
                    # apply_to_job.apply_async(
                    #     args=[user_id, job_id],
                    #     priority=priority,
                    #     countdown=60  # Delay to avoid overwhelming portals
                    # )
                    
                    queued_jobs += 1
                    logger.info(f"Queued job for application: {job.title} at {job.company}")
                
            except Exception as e:
                logger.warning(f"Failed to queue job {job_id}: {e}")
                continue
        
        result = {
            'user_id': user_id,
            'job_ids': job_ids,
            'jobs_queued': queued_jobs,
            'priority': priority,
            'task_id': self.request.id,
            'completed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Job queueing completed: {queued_jobs} jobs queued")
        return result
        
    except Exception as e:
        logger.error(f"Job queueing failed: {e}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="continuous_job_search")
def continuous_job_search(self, user_id: str) -> Dict[str, Any]:
    """Perform continuous job search for a user.
    
    Args:
        user_id: User ID
        
    Returns:
        Dictionary containing search results
    """
    try:
        logger.info(f"Starting continuous job search for user {user_id}")
        
        # Get user to check if they have active search enabled
        user_repo = UserRepository()
        user = user_repo.get_by_id_sync(user_id)
        
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        settings = user.profile.get('settings', {})
        if not settings.get('continuous_search_enabled', False):
            logger.info(f"Continuous search disabled for user {user_id}")
            return {
                'user_id': user_id,
                'status': 'disabled',
                'message': 'Continuous search is disabled for this user'
            }
        
        # Perform job search with user preferences
        search_result = search_jobs_for_user.delay(user_id)
        
        # Schedule next search
        next_search_interval = settings.get('search_interval_hours', 24)
        continuous_job_search.apply_async(
            args=[user_id],
            countdown=next_search_interval * 3600  # Convert hours to seconds
        )
        
        return {
            'user_id': user_id,
            'status': 'scheduled',
            'search_task_id': search_result.id,
            'next_search_in_hours': next_search_interval,
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Continuous job search failed for user {user_id}: {e}")
        raise


@celery_app.task(bind=True, base=CallbackTask, name="cleanup_old_jobs")
def cleanup_old_jobs(self, days_old: int = 30) -> Dict[str, Any]:
    """Clean up old job listings.
    
    Args:
        days_old: Number of days after which jobs are considered old
        
    Returns:
        Dictionary containing cleanup results
    """
    try:
        logger.info(f"Cleaning up jobs older than {days_old} days")
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        job_repo = JobRepository()
        
        # Get old jobs that haven't been applied to
        old_jobs = job_repo.get_old_jobs_sync(cutoff_date, status='discovered')
        
        deleted_count = 0
        for job in old_jobs:
            try:
                job_repo.delete_sync(str(job.id))
                deleted_count += 1
            except Exception as e:
                logger.warning(f"Failed to delete job {job.id}: {e}")
                continue
        
        result = {
            'cutoff_date': cutoff_date.isoformat(),
            'jobs_deleted': deleted_count,
            'task_id': self.request.id,
            'completed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Cleanup completed: {deleted_count} old jobs deleted")
        return result
        
    except Exception as e:
        logger.error(f"Job cleanup failed: {e}")
        raise


# Periodic task setup (will be configured in Celery Beat)
@celery_app.task(name="schedule_continuous_searches")
def schedule_continuous_searches() -> Dict[str, Any]:
    """Schedule continuous searches for all active users."""
    try:
        logger.info("Scheduling continuous searches for active users")
        
        user_repo = UserRepository()
        active_users = user_repo.get_users_with_continuous_search_sync()
        
        scheduled_count = 0
        for user in active_users:
            try:
                continuous_job_search.delay(str(user.id))
                scheduled_count += 1
            except Exception as e:
                logger.warning(f"Failed to schedule search for user {user.id}: {e}")
                continue
        
        return {
            'users_scheduled': scheduled_count,
            'total_active_users': len(active_users),
            'completed_at': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to schedule continuous searches: {e}")
        raise