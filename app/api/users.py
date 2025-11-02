"""User API endpoints for registration and profile management."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, status, Depends
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

from app.services.user_service import UserService
from app.models.user import User, PersonalInfo, Experience, Education, JobPreferences, WorkType
from app.database_utils import NotFoundError, DuplicateError

router = APIRouter()


# Request/Response Models
class UserRegistrationRequest(BaseModel):
    """User registration request model."""
    personal_info: PersonalInfo
    skills: Optional[List[str]] = Field(default_factory=list)
    experience: Optional[List[Experience]] = Field(default_factory=list)
    education: Optional[List[Education]] = Field(default_factory=list)


class UserResponse(BaseModel):
    """User response model."""
    id: str
    personal_info: PersonalInfo
    skills: List[str]
    experience: List[Experience]
    education: List[Education]
    preferences: Optional[Dict[str, Any]] = None
    resume_content: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        """Create UserResponse from User model."""
        return cls(
            id=str(user.id),
            personal_info=user.personal_info,
            skills=user.skills,
            experience=user.experience,
            education=user.education,
            preferences=user.preferences.dict() if user.preferences else None,
            resume_content=user.resume_content,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at
        )


class PersonalInfoUpdateRequest(BaseModel):
    """Personal info update request model."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    linkedin_url: Optional[str] = None


class SkillsUpdateRequest(BaseModel):
    """Skills update request model."""
    skills: List[str] = Field(..., description="List of skills")


class ExperienceRequest(BaseModel):
    """Experience request model."""
    company: str
    position: str
    start_date: datetime
    end_date: Optional[datetime] = None
    description: str
    skills_used: List[str] = Field(default_factory=list)


class EducationRequest(BaseModel):
    """Education request model."""
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    graduation_year: int
    gpa: Optional[float] = None


class ResumeUploadResponse(BaseModel):
    """Resume upload response model."""
    message: str
    parsed_content: Dict[str, Any]
    user: UserResponse


class ProfileStatsResponse(BaseModel):
    """Profile statistics response model."""
    skills_count: int
    experience_count: int
    education_count: int
    has_preferences: bool
    has_resume_content: bool
    profile_completeness: float


class JobPreferencesRequest(BaseModel):
    """Job preferences request model."""
    desired_roles: List[str] = Field(..., min_items=1, description="List of desired job roles")
    locations: List[str] = Field(..., min_items=1, description="Preferred work locations")
    salary_range: Dict[str, int] = Field(..., description="Salary range with min and max")
    company_types: List[str] = Field(default_factory=list, description="Preferred company types")
    work_type: WorkType = Field(default=WorkType.ANY, description="Work arrangement preference")


class JobMatchRequest(BaseModel):
    """Job match calculation request model."""
    title: str
    description: str
    location: str
    requirements: List[str] = Field(default_factory=list)
    salary: Optional[str] = None
    work_type: Optional[str] = None


class JobMatchResponse(BaseModel):
    """Job match calculation response model."""
    match_score: float
    user_id: str
    job_data: Dict[str, Any]


# Dependency to get user service
def get_user_service() -> UserService:
    """Get user service instance."""
    return UserService()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    request: UserRegistrationRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Register a new user."""
    try:
        user = await user_service.register_user(
            personal_info=request.personal_info.dict(),
            skills=request.skills,
            experience=[exp.dict() for exp in request.experience] if request.experience else None,
            education=[edu.dict() for edu in request.education] if request.education else None
        )
        
        return UserResponse.from_user(user)
        
    except DuplicateError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register user"
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Get user by ID."""
    try:
        user = await user_service.get_user_by_id(user_id)
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid user ID format"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )


@router.get("/email/{email}", response_model=UserResponse)
async def get_user_by_email(
    email: str,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Get user by email."""
    try:
        user = await user_service.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse.from_user(user)
        
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user"
        )


@router.put("/{user_id}/personal-info", response_model=UserResponse)
async def update_personal_info(
    user_id: str,
    request: PersonalInfoUpdateRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Update user's personal information."""
    try:
        # Get current user to merge with updates
        current_user = await user_service.get_user_by_id(user_id)
        
        # Merge current data with updates
        updated_info = current_user.personal_info.dict()
        for field, value in request.dict(exclude_unset=True).items():
            if value is not None:
                updated_info[field] = value
        
        user = await user_service.update_personal_info(user_id, updated_info)
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update personal information"
        )


@router.put("/{user_id}/skills", response_model=UserResponse)
async def update_skills(
    user_id: str,
    request: SkillsUpdateRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Update user's skills."""
    try:
        user = await user_service.update_skills(user_id, request.skills)
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update skills"
        )


@router.post("/{user_id}/experience", response_model=UserResponse)
async def add_experience(
    user_id: str,
    request: ExperienceRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Add work experience to user profile."""
    try:
        user = await user_service.add_experience(user_id, request.dict())
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add experience"
        )


@router.put("/{user_id}/experience/{experience_index}", response_model=UserResponse)
async def update_experience(
    user_id: str,
    experience_index: int,
    request: ExperienceRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Update specific work experience."""
    try:
        user = await user_service.update_experience(user_id, experience_index, request.dict())
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update experience"
        )


@router.delete("/{user_id}/experience/{experience_index}", response_model=UserResponse)
async def remove_experience(
    user_id: str,
    experience_index: int,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Remove work experience."""
    try:
        user = await user_service.remove_experience(user_id, experience_index)
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove experience"
        )


@router.post("/{user_id}/education", response_model=UserResponse)
async def add_education(
    user_id: str,
    request: EducationRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Add education to user profile."""
    try:
        user = await user_service.add_education(user_id, request.dict())
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add education"
        )


@router.put("/{user_id}/education/{education_index}", response_model=UserResponse)
async def update_education(
    user_id: str,
    education_index: int,
    request: EducationRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Update specific education entry."""
    try:
        user = await user_service.update_education(user_id, education_index, request.dict())
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update education"
        )


@router.delete("/{user_id}/education/{education_index}", response_model=UserResponse)
async def remove_education(
    user_id: str,
    education_index: int,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Remove education entry."""
    try:
        user = await user_service.remove_education(user_id, education_index)
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove education"
        )


@router.post("/{user_id}/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    user_id: str,
    resume_file: UploadFile = File(...),
    user_service: UserService = Depends(get_user_service)
) -> ResumeUploadResponse:
    """Upload and parse resume file."""
    try:
        user, parsed_content = await user_service.upload_and_parse_resume(user_id, resume_file)
        
        return ResumeUploadResponse(
            message="Resume uploaded and parsed successfully",
            parsed_content=parsed_content,
            user=UserResponse.from_user(user)
        )
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload resume"
        )


@router.get("/{user_id}/stats", response_model=ProfileStatsResponse)
async def get_profile_stats(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
) -> ProfileStatsResponse:
    """Get user profile statistics."""
    try:
        stats = await user_service.get_user_profile_stats(user_id)
        return ProfileStatsResponse(**stats)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get profile statistics"
        )


@router.put("/{user_id}/deactivate", response_model=UserResponse)
async def deactivate_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Deactivate user account."""
    try:
        user = await user_service.deactivate_user(user_id)
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate user"
        )


@router.put("/{user_id}/activate", response_model=UserResponse)
async def activate_user(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Activate user account."""
    try:
        user = await user_service.activate_user(user_id)
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to activate user"
        )

@router.put("/{user_id}/preferences", response_model=UserResponse)
async def update_job_preferences(
    user_id: str,
    request: JobPreferencesRequest,
    user_service: UserService = Depends(get_user_service)
) -> UserResponse:
    """Update user's job preferences."""
    try:
        user = await user_service.update_job_preferences(user_id, request.dict())
        return UserResponse.from_user(user)
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update job preferences"
        )


@router.get("/{user_id}/preferences", response_model=Optional[JobPreferences])
async def get_job_preferences(
    user_id: str,
    user_service: UserService = Depends(get_user_service)
) -> Optional[JobPreferences]:
    """Get user's job preferences."""
    try:
        preferences = await user_service.get_job_preferences(user_id)
        return preferences
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get job preferences"
        )


@router.post("/{user_id}/match-job", response_model=JobMatchResponse)
async def calculate_job_match(
    user_id: str,
    request: JobMatchRequest,
    user_service: UserService = Depends(get_user_service)
) -> JobMatchResponse:
    """Calculate job match score for a user."""
    try:
        match_score = await user_service.calculate_job_match_score(
            user_id, 
            request.dict()
        )
        
        return JobMatchResponse(
            match_score=match_score,
            user_id=user_id,
            job_data=request.dict()
        )
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate job match score"
        )