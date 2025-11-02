"""Job matching service using machine learning algorithms."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from app.models.user import User
from app.models.job import Job
from app.repositories.user_repository import UserRepository
from app.repositories.job_repository import JobRepository


class JobMatchingService:
    """Service for matching jobs to user preferences using ML algorithms."""
    
    def __init__(self):
        """Initialize the job matching service."""
        self.logger = logging.getLogger("job_matching_service")
        self.user_repo = UserRepository()
        self.job_repo = JobRepository()
        
        # Initialize ML components
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            lowercase=True
        )
        self.scaler = StandardScaler()
        
        # Weights for different matching criteria
        self.weights = {
            'skills_match': 0.35,
            'title_match': 0.25,
            'location_match': 0.15,
            'experience_match': 0.15,
            'salary_match': 0.10
        }
    
    async def calculate_job_match_score(
        self, 
        user_id: str, 
        job_id: str
    ) -> Dict[str, Any]:
        """Calculate match score between a user and a job.
        
        Args:
            user_id: User ID
            job_id: Job ID
            
        Returns:
            Dictionary containing match score and breakdown
        """
        try:
            # Get user and job data
            user = await self.user_repo.get_by_id(user_id)
            job = await self.job_repo.get_by_id(job_id)
            
            if not user or not job:
                raise ValueError("User or job not found")
            
            # Calculate individual match scores
            skills_score = self._calculate_skills_match(user, job)
            title_score = self._calculate_title_match(user, job)
            location_score = self._calculate_location_match(user, job)
            experience_score = self._calculate_experience_match(user, job)
            salary_score = self._calculate_salary_match(user, job)
            
            # Calculate weighted overall score
            overall_score = (
                skills_score * self.weights['skills_match'] +
                title_score * self.weights['title_match'] +
                location_score * self.weights['location_match'] +
                experience_score * self.weights['experience_match'] +
                salary_score * self.weights['salary_match']
            )
            
            return {
                'user_id': user_id,
                'job_id': job_id,
                'overall_score': round(overall_score, 2),
                'breakdown': {
                    'skills_match': round(skills_score, 2),
                    'title_match': round(title_score, 2),
                    'location_match': round(location_score, 2),
                    'experience_match': round(experience_score, 2),
                    'salary_match': round(salary_score, 2)
                },
                'weights': self.weights,
                'calculated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating match score: {e}")
            raise
    
    async def batch_calculate_matches(
        self, 
        user_id: str, 
        job_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Calculate match scores for multiple jobs for a user.
        
        Args:
            user_id: User ID
            job_ids: List of job IDs
            
        Returns:
            List of match score dictionaries sorted by score
        """
        matches = []
        
        for job_id in job_ids:
            try:
                match_result = await self.calculate_job_match_score(user_id, job_id)
                matches.append(match_result)
            except Exception as e:
                self.logger.warning(f"Failed to calculate match for job {job_id}: {e}")
                continue
        
        # Sort by overall score (descending)
        matches.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return matches
    
    def batch_calculate_matches_sync(
        self, 
        user_id: str, 
        job_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Synchronous version of batch_calculate_matches for Celery tasks.
        
        Args:
            user_id: User ID
            job_ids: List of job IDs
            
        Returns:
            List of match score dictionaries sorted by score
        """
        matches = []
        
        for job_id in job_ids:
            try:
                match_result = self.calculate_job_match_score_sync(user_id, job_id)
                matches.append(match_result)
            except Exception as e:
                self.logger.warning(f"Failed to calculate match for job {job_id}: {e}")
                continue
        
        # Sort by overall score (descending)
        matches.sort(key=lambda x: x['overall_score'], reverse=True)
        
        return matches
    
    def calculate_job_match_score_sync(
        self, 
        user_id: str, 
        job_id: str
    ) -> Dict[str, Any]:
        """Synchronous version of calculate_job_match_score for Celery tasks.
        
        Args:
            user_id: User ID
            job_id: Job ID
            
        Returns:
            Dictionary containing match score and breakdown
        """
        try:
            # Get user and job data
            user = self.user_repo.get_by_id_sync(user_id)
            job = self.job_repo.get_by_id_sync(job_id)
            
            if not user or not job:
                raise ValueError("User or job not found")
            
            # Calculate individual match scores
            skills_score = self._calculate_skills_match(user, job)
            title_score = self._calculate_title_match(user, job)
            location_score = self._calculate_location_match(user, job)
            experience_score = self._calculate_experience_match(user, job)
            salary_score = self._calculate_salary_match(user, job)
            
            # Calculate weighted overall score
            overall_score = (
                skills_score * self.weights['skills_match'] +
                title_score * self.weights['title_match'] +
                location_score * self.weights['location_match'] +
                experience_score * self.weights['experience_match'] +
                salary_score * self.weights['salary_match']
            )
            
            return {
                'user_id': user_id,
                'job_id': job_id,
                'overall_score': round(overall_score, 2),
                'breakdown': {
                    'skills_match': round(skills_score, 2),
                    'title_match': round(title_score, 2),
                    'location_match': round(location_score, 2),
                    'experience_match': round(experience_score, 2),
                    'salary_match': round(salary_score, 2)
                },
                'weights': self.weights,
                'calculated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error calculating match score: {e}")
            raise
    
    async def find_matching_jobs(
        self, 
        user_id: str, 
        min_score: float = 0.6,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find jobs that match user preferences above a minimum score.
        
        Args:
            user_id: User ID
            min_score: Minimum match score threshold
            limit: Maximum number of jobs to return
            
        Returns:
            List of matching jobs with scores
        """
        try:
            # Get user preferences
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise ValueError("User not found")
            
            # Get available jobs (not yet applied to)
            available_jobs = await self.job_repo.get_available_jobs_for_user(user_id, limit * 2)
            
            # Calculate matches for available jobs
            job_ids = [str(job.id) for job in available_jobs]
            matches = await self.batch_calculate_matches(user_id, job_ids)
            
            # Filter by minimum score and limit results
            filtered_matches = [
                match for match in matches 
                if match['overall_score'] >= min_score
            ][:limit]
            
            # Enrich with job details
            enriched_matches = []
            for match in filtered_matches:
                job = await self.job_repo.get_by_id(match['job_id'])
                if job:
                    enriched_match = {
                        **match,
                        'job_details': {
                            'title': job.title,
                            'company': job.company,
                            'location': job.location,
                            'url': job.url,
                            'portal': job.portal,
                            'posted_date': job.posted_date.isoformat() if job.posted_date else None
                        }
                    }
                    enriched_matches.append(enriched_match)
            
            return enriched_matches
            
        except Exception as e:
            self.logger.error(f"Error finding matching jobs: {e}")
            raise
    
    def _calculate_skills_match(self, user: User, job: Job) -> float:
        """Calculate skills match score using TF-IDF similarity.
        
        Args:
            user: User object
            job: Job object
            
        Returns:
            Skills match score (0-1)
        """
        try:
            # Get user skills
            user_skills = user.profile.get('skills', [])
            if isinstance(user_skills, str):
                user_skills = [user_skills]
            
            # Get job requirements and description
            job_requirements = job.requirements or []
            job_description = job.description or ""
            
            # Combine job text
            job_text = " ".join(job_requirements + [job_description])
            user_text = " ".join(user_skills)
            
            if not user_text.strip() or not job_text.strip():
                return 0.0
            
            # Calculate TF-IDF similarity
            documents = [user_text, job_text]
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(documents)
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            self.logger.warning(f"Error calculating skills match: {e}")
            return 0.0
    
    def _calculate_title_match(self, user: User, job: Job) -> float:
        """Calculate job title match score.
        
        Args:
            user: User object
            job: Job object
            
        Returns:
            Title match score (0-1)
        """
        try:
            # Get user preferred roles
            preferences = user.profile.get('preferences', {})
            desired_roles = preferences.get('desired_roles', [])
            
            if not desired_roles or not job.title:
                return 0.0
            
            job_title_lower = job.title.lower()
            max_score = 0.0
            
            for role in desired_roles:
                role_lower = role.lower()
                
                # Exact match
                if role_lower == job_title_lower:
                    return 1.0
                
                # Partial match
                if role_lower in job_title_lower or job_title_lower in role_lower:
                    max_score = max(max_score, 0.8)
                
                # Keyword match
                role_keywords = set(re.findall(r'\w+', role_lower))
                title_keywords = set(re.findall(r'\w+', job_title_lower))
                
                if role_keywords and title_keywords:
                    overlap = len(role_keywords.intersection(title_keywords))
                    total = len(role_keywords.union(title_keywords))
                    keyword_score = overlap / total if total > 0 else 0
                    max_score = max(max_score, keyword_score * 0.6)
            
            return max_score
            
        except Exception as e:
            self.logger.warning(f"Error calculating title match: {e}")
            return 0.0
    
    def _calculate_location_match(self, user: User, job: Job) -> float:
        """Calculate location match score.
        
        Args:
            user: User object
            job: Job object
            
        Returns:
            Location match score (0-1)
        """
        try:
            preferences = user.profile.get('preferences', {})
            preferred_locations = preferences.get('locations', [])
            work_type = preferences.get('work_type', 'any')
            
            if not preferred_locations or not job.location:
                return 0.5  # Neutral score if no preferences
            
            job_location_lower = job.location.lower()
            
            # Check for remote work
            if work_type in ['remote', 'any'] and any(
                remote_keyword in job_location_lower 
                for remote_keyword in ['remote', 'work from home', 'wfh', 'anywhere']
            ):
                return 1.0
            
            # Check location matches
            for location in preferred_locations:
                location_lower = location.lower()
                
                # Exact match
                if location_lower == job_location_lower:
                    return 1.0
                
                # City/state match
                if location_lower in job_location_lower or job_location_lower in location_lower:
                    return 0.8
                
                # Country match (basic)
                location_parts = set(location_lower.split())
                job_parts = set(job_location_lower.split())
                if location_parts.intersection(job_parts):
                    return 0.6
            
            return 0.2  # Low score for non-matching locations
            
        except Exception as e:
            self.logger.warning(f"Error calculating location match: {e}")
            return 0.5
    
    def _calculate_experience_match(self, user: User, job: Job) -> float:
        """Calculate experience level match score.
        
        Args:
            user: User object
            job: Job object
            
        Returns:
            Experience match score (0-1)
        """
        try:
            # Get user experience
            user_experience = user.profile.get('experience', [])
            total_experience_years = 0
            
            for exp in user_experience:
                if isinstance(exp, dict):
                    years = exp.get('years', 0)
                    if isinstance(years, (int, float)):
                        total_experience_years += years
            
            # Extract experience requirements from job
            job_description = (job.description or "").lower()
            job_requirements = " ".join(job.requirements or []).lower()
            job_text = f"{job_description} {job_requirements}"
            
            # Look for experience patterns
            experience_patterns = [
                r'(\d+)[\s\-\+]*(?:to|-)?\s*(\d+)?\s*(?:years?|yrs?)',
                r'(\d+)\+?\s*(?:years?|yrs?)',
                r'minimum\s*(\d+)\s*(?:years?|yrs?)',
                r'at least\s*(\d+)\s*(?:years?|yrs?)'
            ]
            
            required_years = []
            for pattern in experience_patterns:
                matches = re.findall(pattern, job_text)
                for match in matches:
                    if isinstance(match, tuple):
                        # Range pattern (e.g., "3-5 years")
                        min_years = int(match[0]) if match[0] else 0
                        max_years = int(match[1]) if match[1] else min_years
                        required_years.append((min_years, max_years))
                    else:
                        # Single number pattern
                        years = int(match)
                        required_years.append((years, years))
            
            if not required_years:
                return 0.7  # Neutral score if no experience requirements found
            
            # Calculate best match against requirements
            best_score = 0.0
            for min_req, max_req in required_years:
                if total_experience_years >= min_req and total_experience_years <= max_req + 2:
                    # Perfect match or slightly over
                    best_score = max(best_score, 1.0)
                elif total_experience_years >= min_req:
                    # Over-qualified (diminishing returns)
                    over_years = total_experience_years - max_req
                    score = max(0.6, 1.0 - (over_years * 0.1))
                    best_score = max(best_score, score)
                elif total_experience_years >= min_req * 0.7:
                    # Slightly under-qualified
                    score = 0.7
                    best_score = max(best_score, score)
                else:
                    # Significantly under-qualified
                    score = 0.3
                    best_score = max(best_score, score)
            
            return best_score
            
        except Exception as e:
            self.logger.warning(f"Error calculating experience match: {e}")
            return 0.5
    
    def _calculate_salary_match(self, user: User, job: Job) -> float:
        """Calculate salary match score.
        
        Args:
            user: User object
            job: Job object
            
        Returns:
            Salary match score (0-1)
        """
        try:
            preferences = user.profile.get('preferences', {})
            salary_range = preferences.get('salary_range', {})
            
            if not salary_range or not job.salary:
                return 0.7  # Neutral score if no salary info
            
            user_min = salary_range.get('min', 0)
            user_max = salary_range.get('max', float('inf'))
            
            # Extract salary from job posting
            job_salary_text = job.salary.lower()
            
            # Look for salary patterns
            salary_patterns = [
                r'\$?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)\s*k?',  # $50k, $50,000
                r'(\d{1,3}(?:,\d{3})*)\s*(?:to|-)?\s*(\d{1,3}(?:,\d{3})*)',  # 50-60k
            ]
            
            job_salaries = []
            for pattern in salary_patterns:
                matches = re.findall(pattern, job_salary_text)
                for match in matches:
                    if isinstance(match, tuple) and len(match) == 2:
                        # Range
                        min_sal = self._parse_salary_number(match[0])
                        max_sal = self._parse_salary_number(match[1])
                        if min_sal and max_sal:
                            job_salaries.append((min_sal, max_sal))
                    else:
                        # Single number
                        salary = self._parse_salary_number(match)
                        if salary:
                            job_salaries.append((salary, salary))
            
            if not job_salaries:
                return 0.7  # Neutral if can't parse salary
            
            # Calculate best match
            best_score = 0.0
            for job_min, job_max in job_salaries:
                # Check overlap
                overlap_min = max(user_min, job_min)
                overlap_max = min(user_max, job_max)
                
                if overlap_min <= overlap_max:
                    # There's overlap
                    overlap_size = overlap_max - overlap_min
                    user_range_size = user_max - user_min
                    job_range_size = job_max - job_min
                    
                    if user_range_size > 0 and job_range_size > 0:
                        score = overlap_size / min(user_range_size, job_range_size)
                        best_score = max(best_score, min(1.0, score))
                    else:
                        best_score = max(best_score, 1.0)
                elif job_max < user_min:
                    # Job salary too low
                    gap = user_min - job_max
                    score = max(0.2, 1.0 - (gap / user_min))
                    best_score = max(best_score, score)
                else:
                    # Job salary higher than expected (good)
                    best_score = max(best_score, 0.9)
            
            return best_score
            
        except Exception as e:
            self.logger.warning(f"Error calculating salary match: {e}")
            return 0.7
    
    def _parse_salary_number(self, salary_str: str) -> Optional[int]:
        """Parse salary number from string.
        
        Args:
            salary_str: Salary string
            
        Returns:
            Parsed salary number or None
        """
        try:
            # Remove commas and convert to int
            clean_str = salary_str.replace(',', '').replace('$', '').strip()
            
            # Handle 'k' suffix (thousands)
            if clean_str.endswith('k'):
                return int(float(clean_str[:-1]) * 1000)
            
            return int(float(clean_str))
            
        except (ValueError, AttributeError):
            return None


# Global service instance
job_matching_service = JobMatchingService()