"""User repository with user-specific operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.models.user import User, JobPreferences
from app.repositories.base import BaseRepository
from app.database_utils import handle_db_errors, NotFoundError, DuplicateError


class UserRepository(BaseRepository[User]):
    """Repository for User document operations."""
    
    def __init__(self):
        super().__init__(User)
    
    @handle_db_errors
    async def create_user(self, 
                         personal_info: Dict[str, Any],
                         skills: Optional[List[str]] = None,
                         experience: Optional[List[Dict[str, Any]]] = None,
                         education: Optional[List[Dict[str, Any]]] = None) -> User:
        """Create a new user with profile data."""
        # Check if user with email already exists
        existing_user = await self.find_by_email(personal_info.get('email'))
        if existing_user:
            raise DuplicateError(f"User with email {personal_info['email']} already exists")
        
        user_data = {
            'personal_info': personal_info,
            'skills': skills or [],
            'experience': experience or [],
            'education': education or []
        }
        
        return await self.create(user_data)
    
    @handle_db_errors
    async def find_by_email(self, email: str) -> Optional[User]:
        """Find user by email address."""
        return await self.find_one({"personal_info.email": email})
    
    @handle_db_errors
    async def find_by_email_or_raise(self, email: str) -> User:
        """Find user by email or raise NotFoundError."""
        user = await self.find_by_email(email)
        if not user:
            raise NotFoundError(f"User with email {email} not found")
        return user
    
    @handle_db_errors
    async def update_personal_info(self, user_id: ObjectId, 
                                  personal_info: Dict[str, Any]) -> User:
        """Update user's personal information."""
        user = await self.get_by_id_or_raise(user_id)
        
        # Update personal info fields
        for field, value in personal_info.items():
            if hasattr(user.personal_info, field):
                setattr(user.personal_info, field, value)
        
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def update_skills(self, user_id: ObjectId, skills: List[str]) -> User:
        """Update user's skills list."""
        user = await self.get_by_id_or_raise(user_id)
        user.skills = skills
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def add_skill(self, user_id: ObjectId, skill: str) -> User:
        """Add a skill to user's skills list."""
        user = await self.get_by_id_or_raise(user_id)
        skill = skill.strip()
        
        if skill and skill not in user.skills:
            user.skills.append(skill)
            user.update_timestamp()
            await user.save()
        
        return user
    
    @handle_db_errors
    async def remove_skill(self, user_id: ObjectId, skill: str) -> User:
        """Remove a skill from user's skills list."""
        user = await self.get_by_id_or_raise(user_id)
        skill = skill.strip()
        
        if skill in user.skills:
            user.skills.remove(skill)
            user.update_timestamp()
            await user.save()
        
        return user
    
    @handle_db_errors
    async def update_job_preferences(self, user_id: ObjectId, 
                                   preferences: JobPreferences) -> User:
        """Update user's job preferences."""
        user = await self.get_by_id_or_raise(user_id)
        user.preferences = preferences
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def add_experience(self, user_id: ObjectId, 
                           experience: Dict[str, Any]) -> User:
        """Add work experience to user's profile."""
        user = await self.get_by_id_or_raise(user_id)
        user.experience.append(experience)
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def update_experience(self, user_id: ObjectId, 
                              experience_index: int,
                              experience_data: Dict[str, Any]) -> User:
        """Update specific work experience entry."""
        user = await self.get_by_id_or_raise(user_id)
        
        if 0 <= experience_index < len(user.experience):
            # Update experience fields
            for field, value in experience_data.items():
                if hasattr(user.experience[experience_index], field):
                    setattr(user.experience[experience_index], field, value)
            
            user.update_timestamp()
            await user.save()
        else:
            raise ValueError(f"Experience index {experience_index} out of range")
        
        return user
    
    @handle_db_errors
    async def remove_experience(self, user_id: ObjectId, experience_index: int) -> User:
        """Remove work experience entry."""
        user = await self.get_by_id_or_raise(user_id)
        
        if 0 <= experience_index < len(user.experience):
            user.experience.pop(experience_index)
            user.update_timestamp()
            await user.save()
        else:
            raise ValueError(f"Experience index {experience_index} out of range")
        
        return user
    
    @handle_db_errors
    async def add_education(self, user_id: ObjectId, education: Dict[str, Any]) -> User:
        """Add education to user's profile."""
        user = await self.get_by_id_or_raise(user_id)
        user.education.append(education)
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def update_education(self, user_id: ObjectId,
                             education_index: int,
                             education_data: Dict[str, Any]) -> User:
        """Update specific education entry."""
        user = await self.get_by_id_or_raise(user_id)
        
        if 0 <= education_index < len(user.education):
            # Update education fields
            for field, value in education_data.items():
                if hasattr(user.education[education_index], field):
                    setattr(user.education[education_index], field, value)
            
            user.update_timestamp()
            await user.save()
        else:
            raise ValueError(f"Education index {education_index} out of range")
        
        return user
    
    @handle_db_errors
    async def remove_education(self, user_id: ObjectId, education_index: int) -> User:
        """Remove education entry."""
        user = await self.get_by_id_or_raise(user_id)
        
        if 0 <= education_index < len(user.education):
            user.education.pop(education_index)
            user.update_timestamp()
            await user.save()
        else:
            raise ValueError(f"Education index {education_index} out of range")
        
        return user
    
    @handle_db_errors
    async def update_resume_content(self, user_id: ObjectId, 
                                  resume_content: Dict[str, Any]) -> User:
        """Update user's parsed resume content."""
        user = await self.get_by_id_or_raise(user_id)
        user.resume_content = resume_content
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def deactivate_user(self, user_id: ObjectId) -> User:
        """Deactivate user account."""
        user = await self.get_by_id_or_raise(user_id)
        user.is_active = False
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def activate_user(self, user_id: ObjectId) -> User:
        """Activate user account."""
        user = await self.get_by_id_or_raise(user_id)
        user.is_active = True
        user.update_timestamp()
        await user.save()
        return user
    
    @handle_db_errors
    async def find_active_users(self, limit: Optional[int] = None) -> List[User]:
        """Find all active users."""
        return await self.find_all(
            filter_dict={"is_active": True},
            sort_by="created_at",
            limit=limit
        )
    
    @handle_db_errors
    async def find_users_with_preferences(self) -> List[User]:
        """Find users who have set job preferences."""
        return await self.find_all(
            filter_dict={
                "is_active": True,
                "preferences": {"$ne": None}
            }
        )
    
    @handle_db_errors
    async def search_users_by_skill(self, skill: str) -> List[User]:
        """Search users by skill."""
        return await self.search_text(
            search_term=skill,
            search_fields=["skills"],
            is_active=True
        )
    
    @handle_db_errors
    async def find_users_by_location(self, location: str) -> List[User]:
        """Find users by preferred location."""
        return await self.find_all({
            "is_active": True,
            "preferences.locations": {"$regex": location, "$options": "i"}
        })
    
    @handle_db_errors
    async def get_user_stats(self, user_id: ObjectId) -> Dict[str, Any]:
        """Get user profile statistics."""
        user = await self.get_by_id_or_raise(user_id)
        
        return {
            "skills_count": len(user.skills),
            "experience_count": len(user.experience),
            "education_count": len(user.education),
            "has_preferences": user.preferences is not None,
            "has_resume_content": user.resume_content is not None,
            "profile_completeness": self._calculate_profile_completeness(user)
        }
    
    def _calculate_profile_completeness(self, user: User) -> float:
        """Calculate profile completeness percentage."""
        total_fields = 7
        completed_fields = 0
        
        # Check required fields
        if user.personal_info.first_name and user.personal_info.last_name:
            completed_fields += 1
        if user.personal_info.email:
            completed_fields += 1
        if user.personal_info.phone:
            completed_fields += 1
        if user.skills:
            completed_fields += 1
        if user.experience:
            completed_fields += 1
        if user.education:
            completed_fields += 1
        if user.preferences:
            completed_fields += 1
        
        return (completed_fields / total_fields) * 100
    
    # Synchronous methods for Celery tasks
    
    def get_users_with_continuous_search_sync(self) -> List[User]:
        """Get users with continuous search enabled."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.find_all({
                "is_active": True,
                "profile.settings.continuous_search_enabled": True
            })
        )