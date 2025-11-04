"""User model with profile data and job preferences."""

from dataclasses import field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from beanie import Document
from pydantic import BaseModel, Field, EmailStr, field_validator


class WorkType(str, Enum):
    """Work type preferences."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    ANY = "any"


class JobPreferences(BaseModel):
    """User job search preferences."""
    desired_roles: List[str] = Field(..., min_items=1, description="List of desired job roles")
    locations: List[str] = Field(..., min_items=1, description="Preferred work locations")
    salary_range: Dict[str, int] = Field(..., description="Salary range with min and max")
    company_types: List[str] = Field(default_factory=list, description="Preferred company types")
    work_type: WorkType = Field(default=WorkType.ANY, description="Work arrangement preference")
    
    @field_validator('salary_range')
    def validate_salary_range(cls, v):
        """Validate salary range has min and max keys with valid values."""
        if not isinstance(v, dict):
            raise ValueError('Salary range must be a dictionary')
        if 'min' not in v or 'max' not in v:
            raise ValueError('Salary range must contain min and max keys')
        if not isinstance(v['min'], int) or not isinstance(v['max'], int):
            raise ValueError('Salary min and max must be integers')
        if v['min'] < 0 or v['max'] < 0:
            raise ValueError('Salary values must be positive')
        if v['min'] > v['max']:
            raise ValueError('Minimum salary cannot be greater than maximum salary')
        return v


class PersonalInfo(BaseModel):
    """User personal information."""
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    phone: Optional[str] = Field(None, pattern=r'^\+?[\d\s\-\(\)]+$')
    address: Optional[str] = Field(None, max_length=200)
    linkedin_url: Optional[str] = Field(None, pattern=r'^https://www\.linkedin\.com/in/[\w\-]+/?$')
    
    @field_validator('phone')
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v and len(v.replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('+', '')) < 10:
            raise ValueError('Phone number must be at least 10 digits')
        return v


class Experience(BaseModel):
    """Work experience entry."""
    company: str = Field(..., min_length=1, max_length=100)
    position: str = Field(..., min_length=1, max_length=100)
    start_date: datetime
    end_date: Optional[datetime] = None
    description: str = Field(..., min_length=10, max_length=1000)
    skills_used: List[str] = Field(default_factory=list)
    
    @field_validator('end_date')
    def validate_end_date(cls, v, values):
        """Validate end date is after start date."""
        if v and 'start_date' in values and v < values['start_date']:
            raise ValueError('End date must be after start date')
        return v


class Education(BaseModel):
    """Education entry."""
    institution: str = Field(..., min_length=1, max_length=100)
    degree: str = Field(..., min_length=1, max_length=100)
    field_of_study: Optional[str] = Field(None, max_length=100)
    graduation_year: int = Field(..., ge=1950, le=2030)
    gpa: Optional[float] = Field(None, ge=0.0, le=4.0)


class User(Document):
    """User document model."""
    
    personal_info: PersonalInfo
    skills: List[str] = Field(default_factory=list, description="Technical and soft skills")
    experience: List[Experience] = Field(default_factory=list, description="Work experience history")
    education: List[Education] = Field(default_factory=list, description="Educational background")
    preferences: Optional[JobPreferences] = Field(None, description="Job search preferences")
    resume_content: Optional[Dict[str, Any]] = Field(None, description="Parsed resume content")
    is_active: bool = Field(default=True, description="Whether user account is active")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    hashed_password: str = Field(..., description="Hashed password for authentication")
    
    @field_validator('skills')
    def validate_skills(cls, v):
        """Validate skills list."""
        if len(v) > 50:
            raise ValueError('Maximum 50 skills allowed')
        return [skill.strip() for skill in v if skill.strip()]
    
    @field_validator('experience')
    def validate_experience(cls, v):
        """Validate experience entries."""
        if len(v) > 20:
            raise ValueError('Maximum 20 experience entries allowed')
        return v
    
    @field_validator('education')
    def validate_education(cls, v):
        """Validate education entries."""
        if len(v) > 10:
            raise ValueError('Maximum 10 education entries allowed')
        return v
    
    def update_timestamp(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()
    
    class Settings:
        name = "users"
        # Removed projection to allow hashed_password retrieval for authentication
        indexes = [
            "personal_info.email",
            "is_active",
            "created_at"
        ]