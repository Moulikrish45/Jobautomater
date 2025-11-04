"""Celery tasks for automated job application processing."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from bson import ObjectId

from app.celery_app import celery_app
from app.models.application import ApplicationStatus, ApplicationOutcome

logger = logging.getLogger(__name__)


class ApplicationWorker:
    """Worker class for orchestrating automated job applications."""
    
    def __init__(self, application_id: str):
        self.application_id = application_id
        
    async def execute_application(self) -> Dict[str, Any]:
        """Execute the complete automated application workflow."""
        try:
            # Import services here to avoid circular imports
            from app.services.application_service import ApplicationService
            from app.services.browser_automation_service import BrowserAutomationService
            from app.services.notification_service import notification_service
            from app.repositories.application_repository import application_repository
            from app.repositories.job_repository import job_repository
            from app.repositories.user_repository import user_repository
            from bson import ObjectId
            
            application_service = ApplicationService()
            browser_service = BrowserAutomationService()
            
            # Get application and related data
            application = await application_repository.get_by_id_or_raise(ObjectId(self.application_id))
            job = await job_repository.get_by_id_or_raise(application.job_id)
            user = await user_repository.get_by_id_or_raise(application.user_id)
            
            # Update status to in progress
            await self.update_progress("Starting application automation", 10)
            await application_service.update_application_status(
                self.application_id, 
                ApplicationStatus.IN_PROGRESS
            )
            
            # Send initial notification
            await notification_service.send_user_notification(
                user_id=str(application.user_id),
                notification_type="application_started",
                message=f"Starting application for {job.title} at {job.company}",
                data={
                    "application_id": self.application_id,
                    "job_title": job.title,
                    "company": job.company,
                    "job_id": str(job.id)
                }
            )
            
            # Execute browser automation
            await self.update_progress("Launching browser automation", 20)
            automation_result = await browser_service.apply_to_job(
                job_url=job.url,
                user_profile=user,
                resume_path=self._get_resume_path(application, user),
                application_id=self.application_id
            )
            
            if automation_result["success"]:
                # Application successful
                await self.update_progress("Application submitted successfully", 100)
                
                submission_data = {
                    "confirmation_number": automation_result.get("confirmation_number"),
                    "portal_response": automation_result.get("portal_response"),
                    "form_data": automation_result.get("form_data"),
                    "screenshots": automation_result.get("screenshots", [])
                }
                
                await application_service.complete_application(
                    self.application_id,
                    submission_data,
                    automation_result.get("screenshots", [])
                )
                
                # Send success notification
                await notification_service.send_user_notification(
                    user_id=str(application.user_id),
                    notification_type="application_completed",
                    message=f"Successfully applied to {job.title} at {job.company}",
                    data={
                        "application_id": self.application_id,
                        "job_title": job.title,
                        "company": job.company,
                        "success": True,
                        "confirmation_number": automation_result.get("confirmation_number")
                    }
                )
                
                return {
                    "success": True,
                    "application_id": self.application_id,
                    "confirmation_number": automation_result.get("confirmation_number"),
                    "screenshots": len(automation_result.get("screenshots", []))
                }
                
            else:
                # Application failed
                error_message = automation_result.get("error", "Unknown automation error")
                await self.update_progress(f"Application failed: {error_message}", 0)
                
                await application_service.update_application_status(
                    self.application_id,
                    ApplicationStatus.FAILED,
                    error_message=error_message
                )
                
                # Send failure notification
                await notification_service.send_user_notification(
                    user_id=str(application.user_id),
                    notification_type="application_failed",
                    message=f"Application failed for {job.title}: {error_message}",
                    data={
                        "application_id": self.application_id,
                        "job_title": job.title,
                        "company": job.company,
                        "success": False,
                        "error": error_message
                    }
                )
                
                return {
                    "success": False,
                    "application_id": self.application_id,
                    "error": error_message
                }
                
        except Exception as e:
            logger.error(f"Application workflow failed for {self.application_id}: {e}")
            
            # Update application status to failed
            try:
                from app.services.application_service import ApplicationService
                application_service = ApplicationService()
                await application_service.update_application_status(
                    self.application_id,
                    ApplicationStatus.FAILED,
                    error_message=str(e)
                )
            except Exception as update_error:
                logger.error(f"Failed to update application status: {update_error}")
            
            raise
    
    async def update_progress(self, step: str, progress: int, message: Optional[str] = None):
        """Update application progress and send real-time notifications."""
        try:
            from app.repositories.application_repository import application_repository
            from app.services.notification_service import notification_service
            from bson import ObjectId
            
            # Update application progress in database
            application = await application_repository.get_by_id_or_raise(ObjectId(self.application_id))
            
            # Update progress fields (assuming these exist in the model)
            if hasattr(application, 'progress'):
                if not application.progress:
                    from app.models.application import ApplicationProgress
                    application.progress = ApplicationProgress(
                        current_step=step,
                        progress_percentage=progress,
                        step_start_time=datetime.utcnow(),
                        steps_completed=[],
                        steps_remaining=[]
                    )
                else:
                    application.progress.current_step = step
                    application.progress.progress_percentage = progress
                    application.progress.step_start_time = datetime.utcnow()
            
            application.updated_at = datetime.utcnow()
            await application.save()
            
            # Send real-time WebSocket notification
            await notification_service.send_user_notification(
                user_id=str(application.user_id),
                notification_type="application_progress",
                message=message or step,
                data={
                    "application_id": self.application_id,
                    "step": step,
                    "progress": progress,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to update progress for application {self.application_id}: {e}")
    
    def _get_resume_path(self, application: Application, user) -> Optional[str]:
        """Get the resume file path for the application."""
        # This would integrate with the existing resume system
        # For now, return a placeholder path
        if application.resume_id:
            return f"/app/data/resumes/{application.resume_id}.pdf"
        
        # Fallback to user's default resume
        if hasattr(user, 'default_resume_path'):
            return user.default_resume_path
        
        return None


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def apply_to_job_task(self, application_id: str) -> Dict[str, Any]:
    """
    Main Celery task for automated job application.
    
    This task orchestrates the complete automation workflow:
    1. Initialize browser automation
    2. Navigate to job portal
    3. Fill application form
    4. Submit application
    5. Capture confirmation
    
    Args:
        application_id: ID of the application to process
        
    Returns:
        Dict containing task results and metadata
    """
    try:
        logger.info(f"Starting application automation for {application_id}")
        
        # Create worker instance
        worker = ApplicationWorker(application_id)
        
        # Run the async workflow
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(worker.execute_application())
            logger.info(f"Application automation completed for {application_id}: {result['success']}")
            return result
        finally:
            loop.close()
            
    except Exception as exc:
        logger.error(f"Application task failed for {application_id}: {exc}")
        
        # Update application status to failed
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                from app.services.application_service import ApplicationService
                application_service = ApplicationService()
                loop.run_until_complete(
                    application_service.update_application_status(
                        application_id,
                        ApplicationStatus.FAILED,
                        error_message=str(exc)
                    )
                )
            finally:
                loop.close()
        except Exception as update_error:
            logger.error(f"Failed to update application status after task failure: {update_error}")
        
        # Retry if possible
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying application {application_id} in 60 seconds (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60, exc=exc)
        
        # Final failure
        logger.error(f"Application {application_id} failed permanently after {self.max_retries} retries")
        return {
            "success": False,
            "application_id": application_id,
            "error": str(exc),
            "retries_exhausted": True
        }


@celery_app.task
def cleanup_stale_applications():
    """Periodic task to clean up applications that have been in progress too long."""
    try:
        logger.info("Starting cleanup of stale applications")
        
        # Run async cleanup
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(_async_cleanup_stale_applications())
        finally:
            loop.close()
            
        logger.info("Stale application cleanup completed")
        
    except Exception as e:
        logger.error(f"Failed to cleanup stale applications: {e}")


async def _async_cleanup_stale_applications():
    """Async implementation of stale application cleanup."""
    try:
        from app.repositories.application_repository import application_repository
        from app.services.application_service import ApplicationService
        
        # Find applications that have been in progress for more than 2 hours
        cutoff_time = datetime.utcnow() - timedelta(hours=2)
        
        stale_applications = await application_repository.find_many({
            "status": ApplicationStatus.IN_PROGRESS,
            "updated_at": {"$lt": cutoff_time}
        })
        
        application_service = ApplicationService()
        
        for app in stale_applications:
            try:
                await application_service.update_application_status(
                    str(app.id),
                    ApplicationStatus.FAILED,
                    error_message="Application timed out after 2 hours"
                )
                
                logger.info(f"Marked stale application as failed: {app.id}")
                
            except Exception as e:
                logger.error(f"Failed to cleanup stale application {app.id}: {e}")
        
        logger.info(f"Cleaned up {len(stale_applications)} stale applications")
        
    except Exception as e:
        logger.error(f"Stale application cleanup failed: {e}")
        raise


@celery_app.task
def retry_failed_applications():
    """Periodic task to retry failed applications that are eligible for retry."""
    try:
        logger.info("Processing failed applications for retry")
        
        # Run async retry processing
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(_async_retry_failed_applications())
        finally:
            loop.close()
            
        logger.info("Failed application retry processing completed")
        
    except Exception as e:
        logger.error(f"Failed to process retry applications: {e}")


async def _async_retry_failed_applications():
    """Async implementation of failed application retry processing."""
    try:
        from app.repositories.application_repository import application_repository
        from app.services.application_service import ApplicationService
        
        # Find failed applications that can be retried
        # This would need to be implemented based on your retry logic
        failed_applications = await application_repository.find_many({
            "status": ApplicationStatus.FAILED,
            "retry_count": {"$lt": 3},  # Assuming max 3 retries
            "created_at": {"$gte": datetime.utcnow() - timedelta(days=1)}  # Only retry recent failures
        })
        
        retried_count = 0
        application_service = ApplicationService()
        
        for app in failed_applications:
            try:
                # Reset application for retry
                await application_service.reset_application_for_retry(str(app.id))
                
                # Dispatch new task
                apply_to_job_task.delay(str(app.id))
                
                retried_count += 1
                logger.info(f"Retrying failed application: {app.id}")
                
            except Exception as e:
                logger.error(f"Failed to retry application {app.id}: {e}")
        
        logger.info(f"Retried {retried_count} failed applications")
        
    except Exception as e:
        logger.error(f"Failed application retry processing failed: {e}")
        raise


# Periodic task scheduling
from celery.schedules import crontab

# Add to celery beat schedule
celery_app.conf.beat_schedule.update({
    'cleanup-stale-applications': {
        'task': 'app.tasks.application_tasks.cleanup_stale_applications',
        'schedule': crontab(minute=0),  # Every hour
    },
    'retry-failed-applications': {
        'task': 'app.tasks.application_tasks.retry_failed_applications',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
})