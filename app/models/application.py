"""Application model for tracking job application submissions."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, validator


class ApplicationStatus(str, Enum):
    """Application processing status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApplicationOutcome(str, Enum):
    """Application outcome from employer."""
    APPLIED = "applied"
    VIEWED = "viewed"
    REJECTED = "rejected"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_RECEIVED = "offer_received"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"


class ApplicationAttempt(BaseModel):
    """Individual application attempt record."""
    attempt_number: int = Field(..., ge=1)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    success: bool = Field(default=False)
    error_message: Optional[str] = Field(None, max_length=1000)
    screenshots: List[str] = Field(default_factory=list, description="Screenshot file paths")
    form_data_used: Optional[Dict[str, Any]] = Field(None, description="Form data that was submitted")
    
    @validator('completed_at')
    def validate_completed_at(cls, v, values):
        """Validate completed_at is after started_at."""
        if v and 'started_at' in values and v < values['started_at']:
            raise ValueError('Completion time must be after start time')
        return v
    
    @validator('screenshots')
    def validate_screenshots(cls, v):
        """Validate screenshots list."""
        if len(v) > 20:
            raise ValueError('Maximum 20 screenshots allowed per attempt')
        return v


class SubmissionData(BaseModel):
    """Data submitted in the application."""
    form_fields: Dict[str, Any] = Field(default_factory=dict, description="Form field values")
    resume_filename: Optional[str] = Field(None, description="Name of resume file uploaded")
    cover_letter: Optional[str] = Field(None, max_length=5000, description="Cover letter text")
    additional_documents: List[str] = Field(default_factory=list, description="Additional document filenames")
    submission_id: Optional[str] = Field(None, description="Portal-provided submission ID")
    confirmation_number: Optional[str] = Field(None, description="Application confirmation number")


class Application(Document):
    """Job application tracking document."""
    
    # References
    user_id: PydanticObjectId = Field(..., description="User who submitted the application")
    job_id: PydanticObjectId = Field(..., description="Job that was applied to")
    resume_id: Optional[PydanticObjectId] = Field(None, description="Resume used for this application")
    
    # Application details
    status: ApplicationStatus = Field(default=ApplicationStatus.PENDING, description="Current processing status")
    outcome: Optional[ApplicationOutcome] = Field(None, description="Outcome from employer")
    
    # Submission information
    submission_data: Optional[SubmissionData] = Field(None, description="Data submitted in application")
    attempts: List[ApplicationAttempt] = Field(default_factory=list, description="All application attempts")
    
    # Tracking information
    applied_at: Optional[datetime] = Field(None, description="When application was successfully submitted")
    last_status_check: Optional[datetime] = Field(None, description="Last time status was checked")
    outcome_updated_at: Optional[datetime] = Field(None, description="When outcome was last updated")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Additional tracking
    notes: Optional[str] = Field(None, max_length=2000, description="User or system notes")
    tags: List[str] = Field(default_factory=list, description="User-defined tags")
    
    @validator('attempts')
    def validate_attempts(cls, v):
        """Validate attempts list."""
        if len(v) > 10:
            raise ValueError('Maximum 10 application attempts allowed')
        
        # Validate attempt numbers are sequential
        for i, attempt in enumerate(v):
            if attempt.attempt_number != i + 1:
                raise ValueError('Attempt numbers must be sequential starting from 1')
        
        return v
    
    @validator('tags')
    def validate_tags(cls, v):
        """Validate tags list."""
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return [tag.strip().lower() for tag in v if tag.strip()]
    
    @validator('outcome_updated_at')
    def validate_outcome_updated_at(cls, v, values):
        """Validate outcome_updated_at is after created_at."""
        if v and 'created_at' in values and v < values['created_at']:
            raise ValueError('Outcome update time must be after creation time')
        return v
    
    def add_attempt(self, error_message: Optional[str] = None, 
                   screenshots: Optional[List[str]] = None,
                   form_data: Optional[Dict[str, Any]] = None) -> ApplicationAttempt:
        """Add a new application attempt."""
        attempt_number = len(self.attempts) + 1
        attempt = ApplicationAttempt(
            attempt_number=attempt_number,
            error_message=error_message,
            screenshots=screenshots or [],
            form_data_used=form_data
        )
        self.attempts.append(attempt)
        self.updated_at = datetime.utcnow()
        return attempt
    
    def complete_current_attempt(self, success: bool, 
                               submission_data: Optional[SubmissionData] = None,
                               error_message: Optional[str] = None):
        """Mark the current attempt as completed."""
        if not self.attempts:
            raise ValueError('No attempts to complete')
        
        current_attempt = self.attempts[-1]
        current_attempt.completed_at = datetime.utcnow()
        current_attempt.success = success
        
        if error_message:
            current_attempt.error_message = error_message
        
        if success:
            self.status = ApplicationStatus.COMPLETED
            self.applied_at = datetime.utcnow()
            if submission_data:
                self.submission_data = submission_data
        else:
            self.status = ApplicationStatus.FAILED
        
        self.updated_at = datetime.utcnow()
    
    def update_outcome(self, outcome: ApplicationOutcome, notes: Optional[str] = None):
        """Update application outcome from employer."""
        self.outcome = outcome
        self.outcome_updated_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        
        if notes:
            if self.notes:
                self.notes += f"\n\n{datetime.utcnow().isoformat()}: {notes}"
            else:
                self.notes = f"{datetime.utcnow().isoformat()}: {notes}"
    
    @property
    def total_attempts(self) -> int:
        """Get total number of attempts."""
        return len(self.attempts)
    
    @property
    def successful_attempts(self) -> int:
        """Get number of successful attempts."""
        return sum(1 for attempt in self.attempts if attempt.success)
    
    @property
    def is_completed(self) -> bool:
        """Check if application is completed successfully."""
        return self.status == ApplicationStatus.COMPLETED and self.applied_at is not None
    
    class Settings:
        name = "applications"
        indexes = [
            [("user_id", 1), ("job_id", 1)],  # Compound index for user's job applications
            "user_id",
            "job_id", 
            "status",
            "outcome",
            "applied_at",
            "created_at",
            [("user_id", 1), ("status", 1)],
            [("user_id", 1), ("applied_at", -1)]
        ]