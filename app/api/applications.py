"""Application management API endpoints."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import datetime

from app.services.auth_service import get_current_user
from app.models.user import User
from app.models.application import Application, ApplicationStatus, ApplicationOutcome, SubmissionData
from app.models.job import Job
from app.services.application_service import ApplicationService
from app.services.notification_service import notification_service
from app.tasks.application_tasks import apply_to_job_task

router = APIRouter()


# Request/Response Models
class QueueApplicationRequest(BaseModel):
    """Request to queue a job application."""
    job_id: str = Field(..., description="ID of the job to apply to")
    resume_id: Optional[str] = Field(None, description="Specific resume to use (optional)")
    cover_letter: Optional[str] = Field(None, max_length=5000, description="Custom cover letter")
    notes: Optional[str] = Field(None, max_length=1000, description="Application notes")


class ApplicationResponse(BaseModel):
    """Application response model."""
    id: str
    job_id: str
    status: ApplicationStatus
    outcome: Optional[ApplicationOutcome]
    applied_at: Optional[datetime]
    created_at: datetime
    total_attempts: int
    successful_attempts: int
    notes: Optional[str]
    tags: List[str]
    
    @classmethod
    def from_application(cls, application: Application) -> "ApplicationResponse":
        """Create response from Application model."""
        return cls(
            id=str(application.id),
            job_id=str(application.job_id),
            status=application.status,
            outcome=application.outcome,
            applied_at=application.applied_at,
            created_at=application.created_at,
            total_attempts=application.total_attempts,
            successful_attempts=application.successful_attempts,
            notes=application.notes,
            tags=application.tags
        )


class ApplicationDetailResponse(ApplicationResponse):
    """Detailed application response with attempts."""
    attempts: List[Dict[str, Any]]
    submission_data: Optional[Dict[str, Any]]
    
    @classmethod
    def from_application(cls, application: Application) -> "ApplicationDetailResponse":
        """Create detailed response from Application model."""
        base_data = ApplicationResponse.from_application(application).dict()
        
        return cls(
            **base_data,
            attempts=[
                {
                    "attempt_number": attempt.attempt_number,
                    "started_at": attempt.started_at,
                    "completed_at": attempt.completed_at,
                    "success": attempt.success,
                    "error_message": attempt.error_message,
                    "screenshots": attempt.screenshots
                }
                for attempt in application.attempts
            ],
            submission_data=application.submission_data.dict() if application.submission_data else None
        )


class UpdateOutcomeRequest(BaseModel):
    """Request to update application outcome."""
    outcome: ApplicationOutcome
    notes: Optional[str] = Field(None, max_length=1000)


class ApplicationFilters(BaseModel):
    """Application filtering options."""
    status: Optional[List[ApplicationStatus]] = None
    outcome: Optional[List[ApplicationOutcome]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(default=20, ge=1, le=100)
    skip: int = Field(default=0, ge=0)


# Dependency
def get_application_service() -> ApplicationService:
    """Get application service instance."""
    return ApplicationService()


@router.post("/queue", response_model=ApplicationResponse, status_code=status.HTTP_202_ACCEPTED)
async def queue_application(
    request: QueueApplicationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
) -> ApplicationResponse:
    """Queue a job application for automated processing."""
    try:
        # Validate job exists and is accessible
        job = await app_service.get_job_by_id(request.job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Check if user already applied to this job
        existing_app = await app_service.get_application_by_user_and_job(
            str(current_user.id), 
            request.job_id
        )
        
        if existing_app and existing_app.is_completed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already successfully applied to this job"
            )
        
        # Create or update application
        if existing_app:
            # Reset existing application for retry
            application = await app_service.reset_application_for_retry(
                existing_app.id,
                notes=request.notes
            )
        else:
            # Create new application
            application = await app_service.create_application(
                user_id=str(current_user.id),
                job_id=request.job_id,
                resume_id=request.resume_id,
                cover_letter=request.cover_letter,
                notes=request.notes
            )
        
        # Queue the application task
        task_result = apply_to_job_task.delay(str(application.id))
        
        # Send notification
        await notification_service.notify_application_queued(
            user_id=str(current_user.id),
            job_title=job.title,
            company=job.company,
            application_id=str(application.id)
        )
        
        return ApplicationResponse.from_application(application)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue application: {str(e)}"
        )


@router.get("/", response_model=List[ApplicationResponse])
async def get_user_applications(
    status_filter: Optional[List[ApplicationStatus]] = None,
    outcome_filter: Optional[List[ApplicationOutcome]] = None,
    limit: int = 20,
    skip: int = 0,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
) -> List[ApplicationResponse]:
    """Get user's job applications with filtering."""
    try:
        applications = await app_service.get_user_applications(
            user_id=str(current_user.id),
            status_filter=status_filter,
            outcome_filter=outcome_filter,
            limit=limit,
            skip=skip
        )
        
        return [ApplicationResponse.from_application(app) for app in applications]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve applications: {str(e)}"
        )


@router.get("/{application_id}", response_model=ApplicationDetailResponse)
async def get_application_detail(
    application_id: str,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
) -> ApplicationDetailResponse:
    """Get detailed application information including attempts and screenshots."""
    try:
        application = await app_service.get_application_by_id(application_id)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify user owns this application
        if str(application.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return ApplicationDetailResponse.from_application(application)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve application: {str(e)}"
        )


@router.put("/{application_id}/outcome", response_model=ApplicationResponse)
async def update_application_outcome(
    application_id: str,
    request: UpdateOutcomeRequest,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
) -> ApplicationResponse:
    """Update application outcome (e.g., interview scheduled, rejected)."""
    try:
        application = await app_service.get_application_by_id(application_id)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify user owns this application
        if str(application.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Update outcome
        updated_application = await app_service.update_application_outcome(
            application_id=application_id,
            outcome=request.outcome,
            notes=request.notes
        )
        
        # Send notification
        await notification_service.notify_application_outcome_updated(
            user_id=str(current_user.id),
            application_id=application_id,
            outcome=request.outcome
        )
        
        return ApplicationResponse.from_application(updated_application)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update application outcome: {str(e)}"
        )


@router.delete("/{application_id}")
async def cancel_application(
    application_id: str,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    """Cancel a pending application."""
    try:
        application = await app_service.get_application_by_id(application_id)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify user owns this application
        if str(application.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Can only cancel pending applications
        if application.status != ApplicationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only cancel pending applications"
            )
        
        # Cancel the application
        await app_service.cancel_application(application_id)
        
        return {"message": "Application cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel application: {str(e)}"
        )


@router.get("/{application_id}/screenshots")
async def get_application_screenshots(
    application_id: str,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    """Get screenshots from application attempts."""
    try:
        application = await app_service.get_application_by_id(application_id)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify user owns this application
        if str(application.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get screenshot URLs
        screenshots = await app_service.get_application_screenshots(application_id)
        
        return {
            "application_id": application_id,
            "screenshots": screenshots
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve screenshots: {str(e)}"
        )


@router.get("/{application_id}/screenshots/{screenshot_filename}")
async def serve_screenshot(
    application_id: str,
    screenshot_filename: str,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    """Serve a specific screenshot file."""
    try:
        from fastapi.responses import FileResponse
        from pathlib import Path
        
        application = await app_service.get_application_by_id(application_id)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify user owns this application
        if str(application.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        # Construct screenshot path
        screenshots_dir = Path("data/screenshots")
        screenshot_path = screenshots_dir / screenshot_filename
        
        # Verify file exists and is safe
        if not screenshot_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screenshot not found"
            )
        
        # Verify the file belongs to this application (basic security check)
        if not screenshot_filename.startswith(application_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )

        return FileResponse(
            path=str(screenshot_path),
            media_type="image/png",
            filename=screenshot_filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to serve screenshot"
        )


@router.get("/{application_id}/logs")
async def get_application_logs(
    application_id: str,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
):
    """Get automation logs for an application."""
    try:
        application = await app_service.get_application_by_id(application_id)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify user owns this application
        if str(application.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        logs = []
        if hasattr(application, 'automation_logs') and application.automation_logs:
            logs = application.automation_logs
        elif hasattr(application, 'submission_data') and application.submission_data and hasattr(application.submission_data, 'automation_logs'):
            logs = application.submission_data.automation_logs or []
        
        return {"logs": logs}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve logs"
        )


@router.post("/{application_id}/retry", response_model=ApplicationResponse)
async def retry_application(
    application_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    app_service: ApplicationService = Depends(get_application_service)
) -> ApplicationResponse:
    """Retry a failed application."""
    try:
        application = await app_service.get_application_by_id(application_id)
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify user owns this application
        if str(application.user_id) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Can only retry failed applications
        if application.status != ApplicationStatus.FAILED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only retry failed applications"
            )
        
        # Reset application for retry
        updated_application = await app_service.reset_application_for_retry(application_id)
        
        # Queue the retry task
        from app.tasks.application_tasks import apply_to_job_task
        task_result = apply_to_job_task.delay(application_id)
        
        return ApplicationResponse.from_application(updated_application)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry application: {str(e)}"
        )