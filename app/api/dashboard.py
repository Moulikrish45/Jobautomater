"""Dashboard API endpoints for tracking applications and analytics."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query, Depends, status
from pydantic import BaseModel, Field
from bson import ObjectId

from app.models.application import Application, ApplicationStatus, ApplicationOutcome
from app.models.job import Job, JobStatus, JobPortal
from app.models.user import User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.job_repository import JobRepository
from app.repositories.user_repository import UserRepository
from app.database_utils import NotFoundError
from app.services.auth_service import get_current_user
from app.models.user import User

router = APIRouter()


# Response Models
class ApplicationSummary(BaseModel):
    """Summary of a job application for dashboard display."""
    id: str
    job_title: str
    company_name: str
    portal: str
    status: ApplicationStatus
    outcome: Optional[ApplicationOutcome] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    total_attempts: int
    match_score: float
    job_location: Dict[str, Any]
    
    @classmethod
    def from_application_and_job(cls, application: Application, job: Job) -> "ApplicationSummary":
        """Create ApplicationSummary from Application and Job models."""
        return cls(
            id=str(application.id),
            job_title=job.title,
            company_name=job.company.name,
            portal=job.portal.value,
            status=application.status,
            outcome=application.outcome,
            applied_at=application.applied_at,
            created_at=application.created_at,
            total_attempts=application.total_attempts,
            match_score=job.match_score,
            job_location=job.location.dict()
        )


class ApplicationDetail(BaseModel):
    """Detailed application information."""
    id: str
    user_id: str
    job_id: str
    job_title: str
    company_name: str
    job_url: str
    portal: str
    status: ApplicationStatus
    outcome: Optional[ApplicationOutcome] = None
    applied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    attempts: List[Dict[str, Any]]
    submission_data: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    tags: List[str]
    job_details: Dict[str, Any]
    
    @classmethod
    def from_application_and_job(cls, application: Application, job: Job) -> "ApplicationDetail":
        """Create ApplicationDetail from Application and Job models."""
        return cls(
            id=str(application.id),
            user_id=str(application.user_id),
            job_id=str(application.job_id),
            job_title=job.title,
            company_name=job.company.name,
            job_url=str(job.url),
            portal=job.portal.value,
            status=application.status,
            outcome=application.outcome,
            applied_at=application.applied_at,
            created_at=application.created_at,
            updated_at=application.updated_at,
            attempts=[attempt.dict() for attempt in application.attempts],
            submission_data=application.submission_data.dict() if application.submission_data else None,
            notes=application.notes,
            tags=application.tags,
            job_details={
                "description": job.description,
                "requirements": job.requirements,
                "responsibilities": job.responsibilities,
                "skills_required": job.skills_required,
                "job_type": job.job_type.value if job.job_type else None,
                "experience_level": job.experience_level.value if job.experience_level else None,
                "salary": job.salary.dict() if job.salary else None,
                "location": job.location.dict(),
                "company": job.company.dict(),
                "posted_date": job.posted_date,
                "match_score": job.match_score
            }
        )


class DashboardMetrics(BaseModel):
    """Dashboard analytics and metrics."""
    total_applications: int
    applications_by_status: Dict[str, int]
    applications_by_outcome: Dict[str, int]
    applications_by_portal: Dict[str, int]
    success_rate: float
    response_rate: float
    average_response_time_days: Optional[float] = None
    applications_last_30_days: int
    top_companies: List[Dict[str, Any]]
    recent_activity: List[Dict[str, Any]]


class ApplicationTrend(BaseModel):
    """Application trend data for charts."""
    date: datetime
    applications_count: int
    success_count: int
    response_count: int


class ApplicationFilters(BaseModel):
    """Filters for application queries."""
    status: Optional[List[ApplicationStatus]] = None
    outcome: Optional[List[ApplicationOutcome]] = None
    portal: Optional[List[JobPortal]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    min_match_score: Optional[float] = Field(None, ge=0.0, le=1.0)


# Dependencies
def get_application_repository() -> ApplicationRepository:
    """Get application repository instance."""
    return ApplicationRepository()


def get_job_repository() -> JobRepository:
    """Get job repository instance."""
    return JobRepository()


def get_user_repository() -> UserRepository:
    """Get user repository instance."""
    return UserRepository()


@router.get("/applications", response_model=List[ApplicationSummary])
async def get_my_applications(
    # REMOVED: user_id: str from path
    current_user: User = Depends(get_current_user), # ADDED: Get authenticated user
    status: Optional[List[ApplicationStatus]] = Query(None, description="Filter by application status"),
    outcome: Optional[List[ApplicationOutcome]] = Query(None, description="Filter by application outcome"),
    portal: Optional[List[JobPortal]] = Query(None, description="Filter by job portal"),
    date_from: Optional[datetime] = Query(None, description="Filter applications from this date"),
    date_to: Optional[datetime] = Query(None, description="Filter applications to this date"),
    company: Optional[str] = Query(None, description="Filter by company name (partial match)"),
    job_title: Optional[str] = Query(None, description="Filter by job title (partial match)"),
    min_match_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum match score"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    app_repo: ApplicationRepository = Depends(get_application_repository)
    # REMOVED: job_repo and user_repo dependencies are not needed here anymore
) -> List[ApplicationSummary]:
    """Get the current authenticated user's job applications."""
    try:
        # CHANGE 2: Use the authenticated user's ID directly
        user_id = current_user.id
        
        # Build filters
        filters = ApplicationFilters(
            status=status,
            outcome=outcome,
            portal=portal,
            date_from=date_from,
            date_to=date_to,
            company=company,
            job_title=job_title,
            min_match_score=min_match_score
        )
        
        # Get applications with jobs
        applications_with_jobs = await app_repo.get_applications_with_jobs(
            user_id=user_id, # Use the ID from the token
            filters=filters.dict(exclude_none=True),
            limit=limit,
            skip=skip
        )
        
        # Convert to response models
        result = [ApplicationSummary.from_application_and_job(app, job) for app, job in applications_with_jobs]
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve applications"
        )


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
async def get_my_application_detail(
    # REMOVED: user_id: str from path
    application_id: str,
    current_user: User = Depends(get_current_user), # ADDED: Auth dependency
    app_repo: ApplicationRepository = Depends(get_application_repository),
    job_repo: JobRepository = Depends(get_job_repository)
) -> ApplicationDetail:
    """Get detailed information about one of the current user's applications."""
    try:
        # Get application
        application = await app_repo.get_by_id(ObjectId(application_id))
        
        # CHANGE 4: Security check - ensure the application belongs to the authenticated user
        if not application or application.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Get associated job
        job = await job_repo.get_by_id(application.job_id)
        if not job:
            # This is an data integrity issue, should probably be a 500 error
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Associated job not found"
            )
        
        return ApplicationDetail.from_application_and_job(application, job)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid ID format"
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application details"
        )


@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    # REMOVED: user_id: str from path
    current_user: User = Depends(get_current_user), # ADDED: Auth dependency
    days: int = Query(30, ge=1, le=365, description="Number of days to include in metrics"),
    app_repo: ApplicationRepository = Depends(get_application_repository),
    job_repo: JobRepository = Depends(get_job_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> DashboardMetrics:
    """Get dashboard metrics and analytics for a user."""
    try:
        # CHANGE 5: Use the authenticated user's ID directly
        user_id = current_user.id
        
        # Validate user exists
        user = await user_repo.get_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get metrics from repository
        metrics = await app_repo.get_user_metrics(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return DashboardMetrics(**metrics)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user ID format"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve dashboard metrics"
        )


@router.get("/trends", response_model=List[ApplicationTrend])
async def get_application_trends(
    # REMOVED: user_id: str from path
    current_user: User = Depends(get_current_user), # ADDED: Auth dependency
    days: int = Query(30, ge=7, le=365, description="Number of days for trend data"),
    app_repo: ApplicationRepository = Depends(get_application_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> List[ApplicationTrend]:
    """Get application trend data for charts."""
    try:
        # CHANGE 6: Use the authenticated user's ID directly
        user_id = current_user.id
        
        # Validate user exists
        user = await user_repo.get_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get trend data
        trends = await app_repo.get_application_trends(
            user_id=user_id,
            days=days
        )
        
        return [ApplicationTrend(**trend) for trend in trends]
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user ID format"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve application trends"
        )


@router.put("/applications/{application_id}/outcome")
async def update_application_outcome(
    user_id: str,
    application_id: str,
    outcome: ApplicationOutcome,
    notes: Optional[str] = None,
    app_repo: ApplicationRepository = Depends(get_application_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> Dict[str, str]:
    """Update application outcome manually."""
    try:
        # Validate user exists
        user = await user_repo.get_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get and validate application
        application = await app_repo.get_by_id(ObjectId(application_id))
        if not application or application.user_id != ObjectId(user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Update outcome
        application.update_outcome(outcome, notes)
        await app_repo.update(application)
        
        return {"message": "Application outcome updated successfully"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid ID format"
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update application outcome"
        )


@router.put("/applications/{application_id}/tags")
async def update_application_tags(
    application_id: str,
    tags: List[str],
    app_repo: ApplicationRepository = Depends(get_application_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> Dict[str, str]:
    """Update application tags."""
    try:
        # Validate user exists
        user = await user_repo.get_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get and validate application
        application = await app_repo.get_by_id(ObjectId(application_id))
        if not application or application.user_id != ObjectId(user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Update tags
        application.tags = tags
        application.updated_at = datetime.utcnow()
        await app_repo.update(application)
        
        return {"message": "Application tags updated successfully"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid ID format"
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update application tags"
        )


@router.get("/jobs/queue", response_model=List[Dict[str, Any]])
async def get_job_queue(
    # REMOVED: user_id: str from path
    current_user: User = Depends(get_current_user), # ADDED: Auth dependency
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    job_repo: JobRepository = Depends(get_job_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> List[Dict[str, Any]]:
    """Get jobs queued for application."""
    try:
        # Validate user exists
        user = await user_repo.get_by_id(ObjectId(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get queued jobs
        jobs = await job_repo.get_jobs_by_status(
            user_id=ObjectId(user_id),
            status=JobStatus.QUEUED,
            limit=limit,
            skip=skip
        )
        
        # Convert to response format
        result = []
        for job in jobs:
            result.append({
                "id": str(job.id),
                "title": job.title,
                "company": job.company.name,
                "location": job.location.dict(),
                "portal": job.portal.value,
                "match_score": job.match_score,
                "discovered_at": job.discovered_at,
                "url": str(job.url)
            })
        
        return result
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user ID format"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve job queue"
        )


@router.post("/jobs/{job_id}/skip")
async def skip_job(
    job_id: str,
    reason: Optional[str] = None,
    job_repo: JobRepository = Depends(get_job_repository),
    user_repo: UserRepository = Depends(get_user_repository)
) -> Dict[str, str]:
    """Skip a job in the queue."""
    try:
        # Validate user exists
        user = await user_repo.get_by_id(ObjectId(current_user.id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get and validate job
        job = await job_repo.get_by_id(ObjectId(job_id))
        if not job or job.user_id != ObjectId(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Job not found"
            )
        
        # Update job status
        job.update_status(JobStatus.SKIPPED)
        await job_repo.update(job)
        
        return {"message": "Job skipped successfully"}
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid ID format"
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to skip job"
        )