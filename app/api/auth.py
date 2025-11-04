"""Authentication API endpoints."""

from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field

from app.services.auth_service import auth_service, get_current_user, security
from app.models.user import User, PersonalInfo
from app.config import settings

router = APIRouter()

# Constants
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


# Request/Response Models
class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=50)  # Reduced max length for bcrypt safety


class RegisterRequest(BaseModel):
    """Registration request model."""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=50)  # Reduced max length for bcrypt safety
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    """User response model."""
    id: str
    email: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    is_active: bool
    created_at: str
    
    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        """Create UserResponse from User model."""
        return cls(
            id=str(user.id),
            email=user.personal_info.email,
            first_name=user.personal_info.first_name,
            last_name=user.personal_info.last_name,
            phone=user.personal_info.phone,
            is_active=user.is_active,
            created_at=user.created_at.isoformat()
        )


class ChangePasswordRequest(BaseModel):
    """Change password request model."""
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6, max_length=50)  # Reduced max length for bcrypt safety


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest) -> TokenResponse:
    """Register a new user."""
    try:
        # Create personal info
        personal_info = {
            "first_name": request.first_name,
            "last_name": request.last_name,
            "email": request.email,
            "phone": request.phone
        }
        
        # Register user
        user = await auth_service.register_user_with_password(
            email=request.email,
            password=request.password,
            personal_info=personal_info
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id), "email": user.personal_info.email},
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=access_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.from_user(user).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """Authenticate user and return access token."""
    try:
        # Authenticate user
        user = await auth_service.authenticate_user(request.email, request.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={"sub": str(user.id), "email": user.personal_info.email},
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=access_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.from_user(user).dict()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.from_user(current_user)


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout user (client should discard token)."""
    # In a stateless JWT system, logout is handled client-side by discarding the token
    # For enhanced security, you could implement a token blacklist here
    return {"message": "Successfully logged out"}


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user)
):
    """Change user password."""
    try:
        success = await auth_service.change_password(
            user_id=str(current_user.id),
            current_password=request.current_password,
            new_password=request.new_password
        )
        
        if success:
            return {"message": "Password changed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password change failed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(current_user: User = Depends(get_current_user)) -> TokenResponse:
    """Refresh access token."""
    try:
        # Create new access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth_service.create_access_token(
            data={"sub": str(current_user.id), "email": current_user.personal_info.email},
            expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=access_token,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse.from_user(current_user).dict()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )