"""Service for managing real-time notifications and WebSocket integration."""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from app.models.application import Application, ApplicationStatus
from app.models.job import Job, JobStatus
from app.models.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for managing notifications across the application."""
    
    def __init__(self):
        self._websocket_service = None
        self._notification_queue = asyncio.Queue()
        self._processing_task = None
    
    def set_websocket_service(self, websocket_service):
        """Set the WebSocket service for real-time notifications."""
        self._websocket_service = websocket_service
    
    async def start(self):
        """Start the notification processing task."""
        if self._processing_task is None:
            self._processing_task = asyncio.create_task(self._process_notifications())
            logger.info("Notification service started")
    
    async def stop(self):
        """Stop the notification processing task."""
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
            logger.info("Notification service stopped")
    
    async def _process_notifications(self):
        """Background task to process queued notifications."""
        while True:
            try:
                # Get notification from queue
                notification = await self._notification_queue.get()
                
                # Send via WebSocket if available
                if self._websocket_service:
                    try:
                        await self._send_websocket_notification(notification)
                    except Exception as e:
                        logger.error(f"Failed to send WebSocket notification: {e}")
                
                # Mark task as done
                self._notification_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing notification: {e}")
                await asyncio.sleep(1)
    
    async def _send_websocket_notification(self, notification: Dict[str, Any]):
        """Send notification via WebSocket."""
        notification_type = notification.get("type")
        user_id = notification.get("user_id")
        
        if not user_id:
            logger.warning("Notification missing user_id")
            return
        
        if notification_type == "application_update":
            await self._websocket_service.notify_application_update(
                user_id=user_id,
                application=notification["application"],
                job=notification.get("job")
            )
        elif notification_type == "job_discovered":
            await self._websocket_service.notify_job_discovered(
                user_id=user_id,
                job=notification["job"]
            )
        elif notification_type == "system_error":
            await self._websocket_service.notify_system_error(
                user_id=user_id,
                error_type=notification["error_type"],
                error_message=notification["error_message"],
                context=notification.get("context")
            )
        elif notification_type == "progress_update":
            await self._websocket_service.notify_progress_update(
                user_id=user_id,
                operation=notification["operation"],
                progress=notification["progress"],
                details=notification.get("details")
            )
        elif notification_type == "automation_status":
            await self._websocket_service.notify_automation_status(
                user_id=user_id,
                enabled=notification["enabled"],
                reason=notification.get("reason")
            )
    
    async def queue_notification(self, notification: Dict[str, Any]):
        """Queue a notification for processing."""
        await self._notification_queue.put(notification)
    
    # Convenience methods for common notifications
    
    async def notify_application_started(self, user_id: str, application: Application, job: Job):
        """Notify that an application process has started."""
        await self.queue_notification({
            "type": "application_update",
            "user_id": user_id,
            "application": application,
            "job": job,
            "timestamp": datetime.utcnow()
        })
    
    async def notify_application_completed(self, user_id: str, application: Application, 
                                         job: Job, success: bool):
        """Notify that an application has been completed."""
        await self.queue_notification({
            "type": "application_update",
            "user_id": user_id,
            "application": application,
            "job": job,
            "timestamp": datetime.utcnow()
        })
    
    async def notify_application_failed(self, user_id: str, application: Application, 
                                      job: Job, error_message: str):
        """Notify that an application has failed."""
        await self.queue_notification({
            "type": "application_update",
            "user_id": user_id,
            "application": application,
            "job": job,
            "timestamp": datetime.utcnow()
        })
        
        # Also send as system error
        await self.queue_notification({
            "type": "system_error",
            "user_id": user_id,
            "error_type": "application_failed",
            "error_message": error_message,
            "context": {
                "job_title": job.title,
                "company": job.company.name,
                "application_id": str(application.id)
            },
            "timestamp": datetime.utcnow()
        })
    
    async def notify_job_discovered(self, user_id: str, job: Job):
        """Notify that a new job has been discovered."""
        await self.queue_notification({
            "type": "job_discovered",
            "user_id": user_id,
            "job": job,
            "timestamp": datetime.utcnow()
        })
    
    async def notify_job_search_progress(self, user_id: str, portal: str, 
                                       progress: float, jobs_found: int):
        """Notify job search progress."""
        await self.queue_notification({
            "type": "progress_update",
            "user_id": user_id,
            "operation": f"job_search_{portal}",
            "progress": progress,
            "details": f"Found {jobs_found} jobs on {portal}",
            "timestamp": datetime.utcnow()
        })
    
    async def notify_resume_optimization_progress(self, user_id: str, job_title: str, 
                                                progress: float):
        """Notify resume optimization progress."""
        await self.queue_notification({
            "type": "progress_update",
            "user_id": user_id,
            "operation": "resume_optimization",
            "progress": progress,
            "details": f"Optimizing resume for {job_title}",
            "timestamp": datetime.utcnow()
        })
    
    async def notify_automation_enabled(self, user_id: str, reason: Optional[str] = None):
        """Notify that automation has been enabled."""
        await self.queue_notification({
            "type": "automation_status",
            "user_id": user_id,
            "enabled": True,
            "reason": reason,
            "timestamp": datetime.utcnow()
        })
    
    async def notify_automation_disabled(self, user_id: str, reason: Optional[str] = None):
        """Notify that automation has been disabled."""
        await self.queue_notification({
            "type": "automation_status",
            "user_id": user_id,
            "enabled": False,
            "reason": reason,
            "timestamp": datetime.utcnow()
        })
    
    # Auto-Applier specific notification methods
    
    async def send_user_notification(self, user_id: str, notification_type: str, 
                                   message: str, data: Optional[Dict[str, Any]] = None):
        """Send a user notification with custom type and data."""
        await self.queue_notification({
            "type": notification_type,
            "user_id": user_id,
            "message": message,
            "data": data or {},
            "timestamp": datetime.utcnow()
        })
    
    async def notify_application_queued(self, user_id: str, job_title: str, 
                                      company: str, application_id: str):
        """Notify that an application has been queued."""
        await self.send_user_notification(
            user_id=user_id,
            notification_type="application_queued",
            message=f"Application queued for {job_title} at {company}",
            data={
                "application_id": application_id,
                "job_title": job_title,
                "company": company,
                "status": "queued"
            }
        )
    
    async def notify_application_progress(self, user_id: str, application_id: str,
                                        step: str, progress: int, job_title: str):
        """Notify application progress update."""
        await self.send_user_notification(
            user_id=user_id,
            notification_type="application_progress",
            message=f"Application progress: {step}",
            data={
                "application_id": application_id,
                "job_title": job_title,
                "step": step,
                "progress": progress,
                "status": "in_progress"
            }
        )
    
    async def notify_application_outcome_updated(self, user_id: str, application_id: str,
                                               outcome: str):
        """Notify that application outcome has been updated."""
        await self.send_user_notification(
            user_id=user_id,
            notification_type="application_outcome_updated",
            message=f"Application outcome updated: {outcome}",
            data={
                "application_id": application_id,
                "outcome": outcome
            }
        )
    
    async def notify_system_error(self, user_id: str, error_type: str, 
                                error_message: str, context: Optional[Dict[str, Any]] = None):
        """Notify of a system error."""
        await self.queue_notification({
            "type": "system_error",
            "user_id": user_id,
            "error_type": error_type,
            "error_message": error_message,
            "context": context or {},
            "timestamp": datetime.utcnow()
        })
    
    async def notify_agent_status_change(self, user_id: str, agent_name: str, 
                                       status: str, details: Optional[str] = None):
        """Notify of agent status changes."""
        await self.queue_notification({
            "type": "system_error" if status == "error" else "progress_update",
            "user_id": user_id,
            "operation": f"agent_{agent_name}",
            "progress": 1.0 if status == "active" else 0.0,
            "details": f"Agent {agent_name} is {status}" + (f": {details}" if details else ""),
            "timestamp": datetime.utcnow()
        })
    
    # Batch notification methods
    
    async def notify_daily_summary(self, user_id: str, applications_submitted: int, 
                                 jobs_discovered: int, success_rate: float):
        """Send daily summary notification."""
        await self.queue_notification({
            "type": "progress_update",
            "user_id": user_id,
            "operation": "daily_summary",
            "progress": 1.0,
            "details": f"Today: {applications_submitted} applications, {jobs_discovered} jobs found, {success_rate:.1%} success rate",
            "timestamp": datetime.utcnow()
        })
    
    async def notify_queue_status(self, user_id: str, jobs_queued: int, 
                                applications_pending: int):
        """Notify current queue status."""
        await self.queue_notification({
            "type": "progress_update",
            "user_id": user_id,
            "operation": "queue_status",
            "progress": 1.0,
            "details": f"Queue: {jobs_queued} jobs, {applications_pending} pending applications",
            "timestamp": datetime.utcnow()
        })


# Global notification service instance
notification_service = NotificationService()


async def initialize_notification_service():
    """Initialize the notification service with WebSocket integration."""
    try:
        # Import here to avoid circular imports
        from app.api.websocket import notification_service as ws_notification_service
        
        # Set up WebSocket integration
        notification_service.set_websocket_service(ws_notification_service)
        
        # Start the service
        await notification_service.start()
        
        logger.info("Notification service initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize notification service: {e}")


async def shutdown_notification_service():
    """Shutdown the notification service."""
    await notification_service.stop()


# Export for use in other modules
__all__ = ["notification_service", "initialize_notification_service", "shutdown_notification_service"]