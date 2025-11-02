"""Resume versioning service for tracking resume versions and metadata."""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from app.repositories.resume_repository import resume_repository
from app.models.resume import Resume, ResumeType, OptimizationMetadata
from app.services.pdf_service import pdf_service


class VersionAction(str, Enum):
    """Resume version actions."""
    CREATED = "created"
    OPTIMIZED = "optimized"
    UPDATED = "updated"
    DELETED = "deleted"


class ResumeVersioningError(Exception):
    """Base exception for resume versioning errors."""
    pass


class ResumeVersion:
    """Resume version metadata."""
    
    def __init__(
        self,
        resume_id: str,
        version: int,
        action: VersionAction,
        user_id: str,
        job_id: Optional[str] = None,
        parent_version_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Initialize resume version.
        
        Args:
            resume_id: Resume ID
            version: Version number
            action: Version action
            user_id: User ID
            job_id: Job ID (for optimized versions)
            parent_version_id: Parent version ID
            metadata: Additional metadata
        """
        self.resume_id = resume_id
        self.version = version
        self.action = action
        self.user_id = user_id
        self.job_id = job_id
        self.parent_version_id = parent_version_id
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "resume_id": self.resume_id,
            "version": self.version,
            "action": self.action.value,
            "user_id": self.user_id,
            "job_id": self.job_id,
            "parent_version_id": self.parent_version_id,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


class ResumeVersioningService:
    """Service for managing resume versions and metadata tracking."""
    
    def __init__(self):
        """Initialize versioning service."""
        self.logger = logging.getLogger(__name__)
        self._version_history: Dict[str, List[ResumeVersion]] = {}
    
    async def create_version(
        self,
        resume: Resume,
        action: VersionAction,
        parent_version_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ResumeVersion:
        """Create a new resume version entry.
        
        Args:
            resume: Resume object
            action: Version action
            parent_version_id: Parent version ID
            metadata: Additional metadata
            
        Returns:
            Created resume version
        """
        try:
            # Get current version count for user
            user_versions = await self.get_user_versions(resume.user_id)
            version_number = len(user_versions) + 1
            
            # Create version
            version = ResumeVersion(
                resume_id=str(resume.id),
                version=version_number,
                action=action,
                user_id=resume.user_id,
                job_id=resume.job_id,
                parent_version_id=parent_version_id,
                metadata=metadata
            )
            
            # Store in memory (in production, this would be stored in database)
            if resume.user_id not in self._version_history:
                self._version_history[resume.user_id] = []
            
            self._version_history[resume.user_id].append(version)
            
            self.logger.info(f"Created version {version_number} for resume {resume.id}")
            
            return version
            
        except Exception as e:
            self.logger.error(f"Failed to create version for resume {resume.id}: {e}")
            raise ResumeVersioningError(f"Version creation failed: {e}")
    
    async def get_user_versions(self, user_id: str) -> List[ResumeVersion]:
        """Get all versions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of user's resume versions
        """
        return self._version_history.get(user_id, [])
    
    async def get_resume_versions(self, resume_id: str) -> List[ResumeVersion]:
        """Get all versions for a specific resume.
        
        Args:
            resume_id: Resume ID
            
        Returns:
            List of resume versions
        """
        all_versions = []
        for user_versions in self._version_history.values():
            for version in user_versions:
                if version.resume_id == resume_id:
                    all_versions.append(version)
        
        return sorted(all_versions, key=lambda v: v.created_at)
    
    async def get_version_tree(self, user_id: str) -> Dict[str, Any]:
        """Get version tree showing relationships between resume versions.
        
        Args:
            user_id: User ID
            
        Returns:
            Version tree structure
        """
        versions = await self.get_user_versions(user_id)
        
        # Build tree structure
        tree = {
            "user_id": user_id,
            "total_versions": len(versions),
            "original_resumes": [],
            "optimized_resumes": []
        }
        
        # Group by type
        for version in versions:
            version_data = version.to_dict()
            
            # Get resume details
            try:
                resume = await resume_repository.get_by_id(version.resume_id)
                if resume:
                    version_data["resume_type"] = resume.type.value
                    version_data["file_path"] = resume.file_path
                    
                    if resume.type == ResumeType.ORIGINAL:
                        tree["original_resumes"].append(version_data)
                    else:
                        tree["optimized_resumes"].append(version_data)
            except Exception as e:
                self.logger.warning(f"Failed to get resume details for version {version.resume_id}: {e}")
        
        return tree
    
    async def get_optimization_history(
        self,
        user_id: str,
        job_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get optimization history for user or specific job.
        
        Args:
            user_id: User ID
            job_id: Optional job ID to filter by
            
        Returns:
            List of optimization history entries
        """
        versions = await self.get_user_versions(user_id)
        
        optimization_history = []
        
        for version in versions:
            if version.action == VersionAction.OPTIMIZED:
                if job_id and version.job_id != job_id:
                    continue
                
                # Get resume details
                try:
                    resume = await resume_repository.get_by_id(version.resume_id)
                    if resume and resume.optimization_metadata:
                        history_entry = {
                            "version": version.to_dict(),
                            "optimization_metadata": {
                                "original_resume_id": resume.optimization_metadata.original_resume_id,
                                "keywords_added": resume.optimization_metadata.keywords_added,
                                "optimization_notes": resume.optimization_metadata.optimization_notes,
                                "model_used": resume.optimization_metadata.model_used,
                                "optimization_score": resume.optimization_metadata.optimization_score
                            },
                            "file_path": resume.file_path,
                            "job_id": resume.job_id
                        }
                        optimization_history.append(history_entry)
                except Exception as e:
                    self.logger.warning(f"Failed to get optimization details for version {version.resume_id}: {e}")
        
        # Sort by creation date (newest first)
        optimization_history.sort(key=lambda x: x["version"]["created_at"], reverse=True)
        
        return optimization_history
    
    async def get_version_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get version statistics for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Version statistics
        """
        versions = await self.get_user_versions(user_id)
        
        stats = {
            "total_versions": len(versions),
            "original_count": 0,
            "optimized_count": 0,
            "actions": {action.value: 0 for action in VersionAction},
            "jobs_optimized_for": set(),
            "average_optimization_score": 0.0,
            "latest_version_date": None,
            "first_version_date": None
        }
        
        optimization_scores = []
        
        for version in versions:
            # Count by action
            stats["actions"][version.action.value] += 1
            
            # Track jobs
            if version.job_id:
                stats["jobs_optimized_for"].add(version.job_id)
            
            # Get resume details for type counting and scores
            try:
                resume = await resume_repository.get_by_id(version.resume_id)
                if resume:
                    if resume.type == ResumeType.ORIGINAL:
                        stats["original_count"] += 1
                    else:
                        stats["optimized_count"] += 1
                    
                    # Collect optimization scores
                    if (resume.optimization_metadata and 
                        resume.optimization_metadata.optimization_score > 0):
                        optimization_scores.append(resume.optimization_metadata.optimization_score)
            except Exception as e:
                self.logger.warning(f"Failed to get resume details for stats: {e}")
        
        # Calculate average optimization score
        if optimization_scores:
            stats["average_optimization_score"] = sum(optimization_scores) / len(optimization_scores)
        
        # Convert set to count
        stats["jobs_optimized_for"] = len(stats["jobs_optimized_for"])
        
        # Date ranges
        if versions:
            dates = [v.created_at for v in versions]
            stats["first_version_date"] = min(dates).isoformat()
            stats["latest_version_date"] = max(dates).isoformat()
        
        return stats
    
    async def cleanup_old_versions(
        self,
        user_id: str,
        keep_count: int = 10
    ) -> Dict[str, Any]:
        """Clean up old resume versions, keeping only the most recent ones.
        
        Args:
            user_id: User ID
            keep_count: Number of versions to keep
            
        Returns:
            Cleanup result
        """
        try:
            versions = await self.get_user_versions(user_id)
            
            if len(versions) <= keep_count:
                return {
                    "success": True,
                    "message": f"No cleanup needed. User has {len(versions)} versions (limit: {keep_count})",
                    "deleted_count": 0
                }
            
            # Sort by creation date (oldest first for deletion)
            versions.sort(key=lambda v: v.created_at)
            
            # Keep the most recent versions
            versions_to_delete = versions[:-keep_count]
            deleted_count = 0
            
            for version in versions_to_delete:
                try:
                    # Delete PDF file if exists
                    resume = await resume_repository.get_by_id(version.resume_id)
                    if resume and resume.file_path:
                        await pdf_service.delete_resume_pdf(resume.file_path)
                    
                    # Delete resume record
                    await resume_repository.delete(version.resume_id)
                    
                    # Remove from version history
                    if user_id in self._version_history:
                        self._version_history[user_id] = [
                            v for v in self._version_history[user_id] 
                            if v.resume_id != version.resume_id
                        ]
                    
                    deleted_count += 1
                    
                except Exception as e:
                    self.logger.warning(f"Failed to delete version {version.resume_id}: {e}")
            
            self.logger.info(f"Cleaned up {deleted_count} old versions for user {user_id}")
            
            return {
                "success": True,
                "message": f"Cleaned up {deleted_count} old versions",
                "deleted_count": deleted_count,
                "remaining_count": len(versions) - deleted_count
            }
            
        except Exception as e:
            self.logger.error(f"Version cleanup failed for user {user_id}: {e}")
            raise ResumeVersioningError(f"Version cleanup failed: {e}")


# Global service instance
resume_versioning_service = ResumeVersioningService()