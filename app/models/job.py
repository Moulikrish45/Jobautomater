"""Job model for storing job listings and search results."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field, HttpUrl, validator


class JobPortal(str, Enum):
    """Supported job portals."""
    LINKEDIN = "linkedin"
    INDEED = "indeed"
    NAUKRI = "naukri"


class JobStatus(str, Enum):
    """Job processing status."""
    DISCOVERED = "discovered"
    QUEUED = "queued"
    APPLIED = "applied"
    SKIPPED = "skipped"
    FAILED = "failed"


class JobType(str, Enum):
    """Job type classifications."""
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"


class ExperienceLevel(str, Enum):
    """Experience level requirements."""
    ENTRY_LEVEL = "entry_level"
    MID_LEVEL = "mid_level"
    SENIOR_LEVEL = "senior_level"
    EXECUTIVE = "executive"


class SalaryInfo(BaseModel):
    """Salary information structure."""
    min_salary: Optional[int] = Field(None, ge=0)
    max_salary: Optional[int] = Field(None, ge=0)
    currency: str = Field(default="USD", max_length=3)
    period: str = Field(default="yearly", pattern=r'^(hourly|monthly|yearly)$')
    
    @validator('max_salary')
    def validate_salary_range(cls, v, values):
        """Validate max salary is greater than min salary."""
        if v and 'min_salary' in values and values['min_salary'] and v < values['min_salary']:
            raise ValueError('Maximum salary must be greater than minimum salary')
        return v


class CompanyInfo(BaseModel):
    """Company information structure."""
    name: str = Field(..., min_length=1, max_length=100)
    size: Optional[str] = Field(None, max_length=50)
    industry: Optional[str] = Field(None, max_length=100)
    website: Optional[HttpUrl] = None
    logo_url: Optional[HttpUrl] = None


class JobLocation(BaseModel):
    """Job location information."""
    city: Optional[str] = Field(None, max_length=50)
    state: Optional[str] = Field(None, max_length=50)
    country: str = Field(..., max_length=50)
    is_remote: bool = Field(default=False)
    is_hybrid: bool = Field(default=False)


class Job(Document):
    """Job listing document model."""
    
    # External identifiers
    external_id: str = Field(..., description="Unique ID from job portal")
    portal: JobPortal = Field(..., description="Source job portal")
    url: HttpUrl = Field(..., description="Original job posting URL")
    
    # Basic job information
    title: str = Field(..., min_length=1, max_length=200, description="Job title")
    company: CompanyInfo = Field(..., description="Company information")
    location: JobLocation = Field(..., description="Job location details")
    
    # Job details
    description: str = Field(..., min_length=10, description="Full job description")
    requirements: List[str] = Field(default_factory=list, description="Job requirements and qualifications")
    responsibilities: List[str] = Field(default_factory=list, description="Job responsibilities")
    skills_required: List[str] = Field(default_factory=list, description="Required technical skills")
    
    # Job classification
    job_type: Optional[JobType] = Field(None, description="Employment type")
    experience_level: Optional[ExperienceLevel] = Field(None, description="Required experience level")
    salary: Optional[SalaryInfo] = Field(None, description="Salary information")
    
    # Matching and processing
    match_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Relevance score for user")
    status: JobStatus = Field(default=JobStatus.DISCOVERED, description="Processing status")
    user_id: PydanticObjectId = Field(..., description="User who this job is relevant for")
    
    # Metadata
    posted_date: Optional[datetime] = Field(None, description="When job was posted on portal")
    discovered_at: datetime = Field(default_factory=datetime.utcnow, description="When job was discovered")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    
    # Additional data
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw scraped data for debugging")
    
    @validator('requirements')
    def validate_requirements(cls, v):
        """Validate requirements list."""
        if len(v) > 50:
            raise ValueError('Maximum 50 requirements allowed')
        return [req.strip() for req in v if req.strip()]
    
    @validator('responsibilities')
    def validate_responsibilities(cls, v):
        """Validate responsibilities list."""
        if len(v) > 50:
            raise ValueError('Maximum 50 responsibilities allowed')
        return [resp.strip() for resp in v if resp.strip()]
    
    @validator('skills_required')
    def validate_skills_required(cls, v):
        """Validate required skills list."""
        if len(v) > 30:
            raise ValueError('Maximum 30 required skills allowed')
        return [skill.strip().lower() for skill in v if skill.strip()]
    
    @validator('description')
    def validate_description_length(cls, v):
        """Validate description is not too long."""
        if len(v) > 10000:
            raise ValueError('Job description cannot exceed 10,000 characters')
        return v.strip()
    
    def update_match_score(self, score: float):
        """Update match score and timestamp."""
        if not 0.0 <= score <= 1.0:
            raise ValueError('Match score must be between 0.0 and 1.0')
        self.match_score = score
        self.last_updated = datetime.utcnow()
    
    def update_status(self, status: JobStatus):
        """Update job status and timestamp."""
        self.status = status
        self.last_updated = datetime.utcnow()
    
    class Settings:
        name = "jobs"
        indexes = [
            [("external_id", 1), ("portal", 1)],  # Compound unique index
            "user_id",
            "status",
            "match_score",
            "posted_date",
            "discovered_at",
            [("user_id", 1), ("status", 1)],
            [("user_id", 1), ("match_score", -1)]
        ]