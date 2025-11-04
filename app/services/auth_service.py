"""Authentication service for user login/logout and JWT management."""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
# Removed passlib import - using bcrypt directly
from fastapi import HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
import logging

from app.config import settings
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.database_utils import NotFoundError

logger = logging.getLogger(__name__)

# Password hashing - use bcrypt directly to avoid passlib issues
import bcrypt

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

security = HTTPBearer()


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self):
        self.user_repository = UserRepository()
    
    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt directly."""
        try:
            # Convert password to bytes
            password_bytes = password.encode('utf-8')
            
            # Bcrypt has a 72 byte limit
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
                logger.warning(f"Password truncated to 72 bytes")
            
            # Generate salt and hash
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            
            # Return as string
            return hashed.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Password hashing failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password hashing failed"
            )
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash using bcrypt directly."""
        try:
            # Convert to bytes
            password_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            
            # Bcrypt has a 72 byte limit
            if len(password_bytes) > 72:
                password_bytes = password_bytes[:72]
            
            # Verify password
            return bcrypt.checkpw(password_bytes, hashed_bytes)
            
        except Exception as e:
            logger.error(f"Password verification failed: {e}")
            return False
    
    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        try:
            user = await self.user_repository.find_by_email(email)
            if not user:
                return None
            
            if not self.verify_password(password, user.hashed_password):
                return None
            
            if not user.is_active:
                return None
            
            return user
            
        except Exception as e:
            logger.error(f"Authentication failed for {email}: {e}")
            return None
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials) -> User:
        """Get current user from JWT token."""
        try:
            payload = self.verify_token(credentials.credentials)
            user_id: str = payload.get("sub")
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            user = await self.user_repository.get_by_id_or_raise(ObjectId(user_id))
            
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Inactive user"
                )
            
            return user
            
        except NotFoundError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    async def register_user_with_password(self, email: str, password: str, 
                                        personal_info: Dict[str, Any]) -> User:
        """Register a new user with hashed password."""
        try:
            # Check if user already exists
            existing_user = await self.user_repository.find_by_email(email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User with this email already exists"
                )
            
            # Hash password
            hashed_password = self.hash_password(password)
            
            # Create user data
            user_data = {
                'personal_info': personal_info,
                'hashed_password': hashed_password,
                'skills': [],
                'experience': [],
                'education': []
            }
            
            user = await self.user_repository.create(user_data)
            logger.info(f"User registered successfully: {email}")
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"User registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )
    
    async def change_password(self, user_id: str, current_password: str, 
                            new_password: str) -> bool:
        """Change user password."""
        try:
            user = await self.user_repository.get_by_id_or_raise(ObjectId(user_id))
            
            # Verify current password
            if not self.verify_password(current_password, user.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is incorrect"
                )
            
            # Hash new password
            new_hashed_password = self.hash_password(new_password)
            
            # Update user
            user.hashed_password = new_hashed_password
            user.update_timestamp()
            await user.save()
            
            logger.info(f"Password changed for user: {user_id}")
            return True
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Password change failed for user {user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Password change failed"
            )


# Global auth service instance
auth_service = AuthService()


# Dependency functions for FastAPI
async def get_current_user(credentials: HTTPAuthorizationCredentials = security) -> User:
    """FastAPI dependency to get current authenticated user."""
    return await auth_service.get_current_user(credentials)


async def get_current_active_user(current_user: User = get_current_user) -> User:
    """FastAPI dependency to get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    return current_user