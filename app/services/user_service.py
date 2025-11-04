"""User service for business logic and operations."""

import os
import json
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
from bson import ObjectId
from fastapi import UploadFile
import PyPDF2
import docx
import logging

from app.models.user import User, PersonalInfo, JobPreferences, Experience, Education
from app.repositories.user_repository import UserRepository
from app.database_utils import NotFoundError, DuplicateError
from app.services.audit_service import audit_service, AuditEventType, AuditSeverity

logger = logging.getLogger(__name__)


class UserService:
    """Service layer for user operations."""
    
    def __init__(self):
        self.user_repository = UserRepository()
    
    async def register_user(self, 
                           personal_info: Dict[str, Any],
                           skills: Optional[List[str]] = None,
                           experience: Optional[List[Dict[str, Any]]] = None,
                           education: Optional[List[Dict[str, Any]]] = None) -> User:
        """Register a new user with profile data."""
        try:
            # Validate personal info by creating PersonalInfo model
            personal_info_model = PersonalInfo(**personal_info)
            
            # Create user
            user = await self.user_repository.create_user(
                personal_info=personal_info_model.dict(),
                skills=skills or [],
                experience=experience or [],
                education=education or []
            )
            
            logger.info(f"User registered successfully: {user.personal_info.email}")
            
            # Log audit event
            audit_service.log_user_event(
                event_type=AuditEventType.USER_CREATED,
                user_id=user.id,
                action="register_user",
                details={
                    "email": user.personal_info.email,
                    "skills_count": len(skills or []),
                    "experience_count": len(experience or []),
                    "education_count": len(education or [])
                },
                severity=AuditSeverity.MEDIUM
            )
            
            return user
            
        except DuplicateError:
            logger.warning(f"Registration failed - user already exists: {personal_info.get('email')}")
            raise
        except Exception as e:
            logger.error(f"User registration failed: {str(e)}")
            raise
    
    async def get_user_by_id(self, user_id: str) -> User:
        """Get user by ID."""
        try:
            return await self.user_repository.get_by_id_or_raise(ObjectId(user_id))
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {str(e)}")
            raise
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        try:
            return await self.user_repository.find_by_email(email)
        except Exception as e:
            logger.error(f"Failed to get user by email {email}: {str(e)}")
            raise
    
    async def update_personal_info(self, user_id: str, 
                                  personal_info: Dict[str, Any]) -> User:
        """Update user's personal information."""
        try:
            # Validate personal info
            personal_info_model = PersonalInfo(**personal_info)
            
            user = await self.user_repository.update_personal_info(
                ObjectId(user_id), 
                personal_info_model.dict()
            )
            
            logger.info(f"Personal info updated for user: {user_id}")
            
            # Log audit event
            audit_service.log_user_event(
                event_type=AuditEventType.USER_UPDATED,
                user_id=user_id,
                action="update_personal_info",
                details={"updated_fields": list(personal_info.keys())},
                severity=AuditSeverity.LOW
            )
            
            return user
            
        except Exception as e:
            logger.error(f"Failed to update personal info for user {user_id}: {str(e)}")
            raise
    
    async def update_skills(self, user_id: str, skills: List[str]) -> User:
        """Update user's skills."""
        try:
            user = await self.user_repository.update_skills(ObjectId(user_id), skills)
            logger.info(f"Skills updated for user: {user_id}")
            return user
        except Exception as e:
            logger.error(f"Failed to update skills for user {user_id}: {str(e)}")
            raise
    
    async def add_experience(self, user_id: str, experience_data: Dict[str, Any]) -> User:
        """Add work experience to user profile."""
        try:
            # Validate experience data
            experience = Experience(**experience_data)
            
            user = await self.user_repository.add_experience(
                ObjectId(user_id), 
                experience.dict()
            )
            
            logger.info(f"Experience added for user: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to add experience for user {user_id}: {str(e)}")
            raise
    
    async def update_experience(self, user_id: str, experience_index: int,
                              experience_data: Dict[str, Any]) -> User:
        """Update specific work experience."""
        try:
            # Validate experience data
            experience = Experience(**experience_data)
            
            user = await self.user_repository.update_experience(
                ObjectId(user_id), 
                experience_index,
                experience.model_dump()
            )
            
            logger.info(f"Experience updated for user: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to update experience for user {user_id}: {str(e)}")
            raise
    
    async def remove_experience(self, user_id: str, experience_index: int) -> User:
        """Remove work experience."""
        try:
            user = await self.user_repository.remove_experience(
                ObjectId(user_id), 
                experience_index
            )
            
            logger.info(f"Experience removed for user: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to remove experience for user {user_id}: {str(e)}")
            raise
    
    async def add_education(self, user_id: str, education_data: Dict[str, Any]) -> User:
        """Add education to user profile."""
        try:
            # Validate education data
            education = Education(**education_data)
            
            user = await self.user_repository.add_education(
                ObjectId(user_id), 
                education.model_dump()
            )
            
            logger.info(f"Education added for user: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to add education for user {user_id}: {str(e)}")
            raise
    
    async def update_education(self, user_id: str, education_index: int,
                             education_data: Dict[str, Any]) -> User:
        """Update specific education entry."""
        try:
            # Validate education data
            education = Education(**education_data)
            
            user = await self.user_repository.update_education(
                ObjectId(user_id), 
                education_index,
                education.model_dump()
            )
            
            logger.info(f"Education updated for user: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to update education for user {user_id}: {str(e)}")
            raise
    
    async def remove_education(self, user_id: str, education_index: int) -> User:
        """Remove education entry."""
        try:
            user = await self.user_repository.remove_education(
                ObjectId(user_id), 
                education_index
            )
            
            logger.info(f"Education removed for user: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to remove education for user {user_id}: {str(e)}")
            raise
    
    async def upload_and_parse_resume(self, user_id: str, 
                                    resume_file: UploadFile) -> Tuple[User, Dict[str, Any]]:
        """Upload and parse resume file."""
        try:
            # Validate file type
            allowed_types = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
            if resume_file.content_type not in allowed_types:
                raise ValueError("Only PDF and DOCX files are supported")
            
            # Read file content
            content = await resume_file.read()
            
            # Parse resume based on file type
            if resume_file.content_type == 'application/pdf':
                parsed_content = self._parse_pdf_resume(content)
            else:  # DOCX
                parsed_content = self._parse_docx_resume(content)
            
            # Update user with parsed resume content
            user = await self.user_repository.update_resume_content(
                ObjectId(user_id), 
                parsed_content.model_dump()
            )
            
            logger.info(f"Resume uploaded and parsed for user: {user_id}")
            return user, parsed_content
            
        except Exception as e:
            logger.error(f"Failed to upload resume for user {user_id}: {str(e)}")
            raise
    
    def _parse_pdf_resume(self, content: bytes) -> Dict[str, Any]:
        """Parse PDF resume content."""
        try:
            import io
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return self._extract_resume_sections(text)
            
        except Exception as e:
            logger.error(f"Failed to parse PDF resume: {str(e)}")
            return {"raw_text": "Failed to parse PDF content", "error": str(e)}
    
    def _parse_docx_resume(self, content: bytes) -> Dict[str, Any]:
        """Parse DOCX resume content."""
        try:
            import io
            docx_file = io.BytesIO(content)
            doc = docx.Document(docx_file)
            
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            return self._extract_resume_sections(text)
            
        except Exception as e:
            logger.error(f"Failed to parse DOCX resume: {str(e)}")
            return {"raw_text": "Failed to parse DOCX content", "error": str(e)}
    
    def _extract_resume_sections(self, text: str) -> Dict[str, Any]:
        """Extract structured information from resume text."""
        # Basic text processing to extract sections
        # This is a simplified implementation - in production, you'd use NLP libraries
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        sections = {
            "raw_text": text,
            "extracted_skills": [],
            "extracted_experience": [],
            "extracted_education": [],
            "contact_info": {},
            "summary": ""
        }
        
        # Simple keyword-based extraction
        skill_keywords = ['python', 'javascript', 'java', 'react', 'node.js', 'sql', 'mongodb', 
                         'aws', 'docker', 'kubernetes', 'git', 'html', 'css', 'typescript']
        
        for line in lines:
            line_lower = line.lower()
            
            # Extract skills
            for skill in skill_keywords:
                if skill in line_lower and skill not in sections["extracted_skills"]:
                    sections["extracted_skills"].append(skill.title())
            
            # Extract email
            if '@' in line and not sections["contact_info"].get("email"):
                import re
                email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', line)
                if email_match:
                    sections["contact_info"]["email"] = email_match.group()
            
            # Extract phone
            if not sections["contact_info"].get("phone"):
                import re
                phone_match = re.search(r'[\+]?[1-9]?[0-9]{7,14}', line)
                if phone_match and len(phone_match.group()) >= 10:
                    sections["contact_info"]["phone"] = phone_match.group()
        
        # Extract first few lines as summary
        if len(lines) > 0:
            sections["summary"] = ' '.join(lines[:3])
        
        return sections
    
    async def get_user_profile_stats(self, user_id: str) -> Dict[str, Any]:
        """Get user profile statistics."""
        try:
            return await self.user_repository.get_user_stats(ObjectId(user_id))
        except Exception as e:
            logger.error(f"Failed to get profile stats for user {user_id}: {str(e)}")
            raise
    
    async def deactivate_user(self, user_id: str) -> User:
        """Deactivate user account."""
        try:
            user = await self.user_repository.deactivate_user(ObjectId(user_id))
            logger.info(f"User deactivated: {user_id}")
            return user
        except Exception as e:
            logger.error(f"Failed to deactivate user {user_id}: {str(e)}")
            raise
    
    async def activate_user(self, user_id: str) -> User:
        """Activate user account."""
        try:
            user = await self.user_repository.activate_user(ObjectId(user_id))
            logger.info(f"User activated: {user_id}")
            return user
        except Exception as e:
            logger.error(f"Failed to activate user {user_id}: {str(e)}")
            raise
    
    async def update_job_preferences(self, user_id: str, 
                                   preferences: Dict[str, Any]) -> User:
        """Update user's job preferences."""
        try:
            # Validate preferences by creating JobPreferences model
            preferences_model = JobPreferences(**preferences)
            
            user = await self.user_repository.update_job_preferences(
                ObjectId(user_id), 
                preferences_model
            )
            
            logger.info(f"Job preferences updated for user: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"Failed to update job preferences for user {user_id}: {str(e)}")
            raise
    
    async def get_job_preferences(self, user_id: str) -> Optional[JobPreferences]:
        """Get user's job preferences."""
        try:
            user = await self.user_repository.get_by_id_or_raise(ObjectId(user_id))
            return user.preferences
        except Exception as e:
            logger.error(f"Failed to get job preferences for user {user_id}: {str(e)}")
            raise
    
    async def calculate_job_match_score(self, user_id: str, 
                                      job_data: Dict[str, Any]) -> float:
        """Calculate job match score based on user preferences."""
        try:
            user = await self.user_repository.get_by_id_or_raise(ObjectId(user_id))
            
            if not user.preferences:
                return 0.0
            
            score = 0.0
            max_score = 100.0
            
            # Role matching (30% weight)
            role_score = self._calculate_role_match(
                user.preferences.desired_roles, 
                job_data.get('title', ''), 
                job_data.get('description', '')
            )
            score += role_score * 0.3
            
            # Location matching (25% weight)
            location_score = self._calculate_location_match(
                user.preferences.locations,
                job_data.get('location', '')
            )
            score += location_score * 0.25
            
            # Skills matching (25% weight)
            skills_score = self._calculate_skills_match(
                user.skills,
                job_data.get('requirements', []),
                job_data.get('description', '')
            )
            score += skills_score * 0.25
            
            # Salary matching (10% weight)
            salary_score = self._calculate_salary_match(
                user.preferences.salary_range,
                job_data.get('salary', '')
            )
            score += salary_score * 0.1
            
            # Work type matching (10% weight)
            work_type_score = self._calculate_work_type_match(
                user.preferences.work_type,
                job_data.get('description', ''),
                job_data.get('work_type', '')
            )
            score += work_type_score * 0.1
            
            return min(score, max_score)
            
        except Exception as e:
            logger.error(f"Failed to calculate job match score for user {user_id}: {str(e)}")
            return 0.0
    
    def _calculate_role_match(self, desired_roles: List[str], 
                            job_title: str, job_description: str) -> float:
        """Calculate role matching score."""
        if not desired_roles:
            return 0.0
        
        job_text = f"{job_title} {job_description}".lower()
        matches = 0
        
        for role in desired_roles:
            role_keywords = role.lower().split()
            for keyword in role_keywords:
                if keyword in job_text:
                    matches += 1
                    break
        
        return (matches / len(desired_roles)) * 100
    
    def _calculate_location_match(self, preferred_locations: List[str], 
                                job_location: str) -> float:
        """Calculate location matching score."""
        if not preferred_locations:
            return 0.0
        
        job_location_lower = job_location.lower()
        
        for location in preferred_locations:
            location_lower = location.lower()
            if location_lower in job_location_lower or job_location_lower in location_lower:
                return 100.0
            
            # Check for remote work
            if 'remote' in location_lower and 'remote' in job_location_lower:
                return 100.0
        
        return 0.0
    
    def _calculate_skills_match(self, user_skills: List[str], 
                              job_requirements: List[str], 
                              job_description: str) -> float:
        """Calculate skills matching score."""
        if not user_skills:
            return 0.0
        
        job_text = f"{' '.join(job_requirements)} {job_description}".lower()
        matches = 0
        
        for skill in user_skills:
            if skill.lower() in job_text:
                matches += 1
        
        return (matches / len(user_skills)) * 100
    
    def _calculate_salary_match(self, salary_range: Dict[str, int], 
                              job_salary: str) -> float:
        """Calculate salary matching score."""
        if not job_salary or not salary_range:
            return 50.0  # Neutral score if no salary info
        
        # Extract numbers from salary string
        import re
        salary_numbers = re.findall(r'\d+', job_salary.replace(',', ''))
        
        if not salary_numbers:
            return 50.0
        
        # Take the highest number as the salary
        job_salary_amount = max([int(num) for num in salary_numbers])
        
        # Check if job salary is within user's range
        if salary_range['min'] <= job_salary_amount <= salary_range['max']:
            return 100.0
        elif job_salary_amount >= salary_range['min']:
            return 80.0  # Above minimum but over maximum
        else:
            return 20.0  # Below minimum
    
    def _calculate_work_type_match(self, preferred_work_type: str, 
                                 job_description: str, job_work_type: str) -> float:
        """Calculate work type matching score."""
        if preferred_work_type == 'any':
            return 100.0
        
        job_text = f"{job_description} {job_work_type}".lower()
        
        if preferred_work_type.lower() in job_text:
            return 100.0
        
        return 0.0