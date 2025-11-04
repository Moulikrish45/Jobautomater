"""Resume repository with resume-specific operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import DESCENDING
from app.models.resume import Resume, ResumeType, ResumeFormat
from app.repositories.base import BaseRepository
from app.database_utils import handle_db_errors, NotFoundError


class ResumeRepository(BaseRepository[Resume]):
    """Repository for Resume document operations."""
    
    def __init__(self):
        super().__init__(Resume)
    
    @handle_db_errors
    async def create_resume(self, 
                          user_id: ObjectId,
                          resume_type: ResumeType,
                          content: Dict[str, Any],
                          job_id: Optional[ObjectId] = None,
                          file_info: Optional[Dict[str, Any]] = None,
                          optimization_metadata: Optional[Dict[str, Any]] = None) -> Resume:
        """Create a new resume."""
        # Get next version number for this user and type
        version = await self._get_next_version(user_id, resume_type)
        
        resume_data = {
            'user_id': user_id,
            'job_id': job_id,
            'type': resume_type,
            'version': version,
            'content': content,
            'file_info': file_info,
            'optimization_metadata': optimization_metadata
        }
        
        return await self.create(resume_data)
    
    @handle_db_errors
    async def find_by_user(self, user_id: ObjectId,
                          resume_type: Optional[ResumeType] = None,
                          is_active: Optional[bool] = None,
                          limit: Optional[int] = None) -> List[Resume]:
        """Find resumes for a specific user."""
        filter_dict = {"user_id": user_id}
        
        if resume_type:
            filter_dict["type"] = resume_type
        if is_active is not None:
            filter_dict["is_active"] = is_active
        
        return await self.find_all(
            filter_dict=filter_dict,
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_by_job(self, job_id: ObjectId,
                         user_id: Optional[ObjectId] = None) -> List[Resume]:
        """Find resumes optimized for a specific job."""
        filter_dict = {"job_id": job_id}
        if user_id:
            filter_dict["user_id"] = user_id
        
        return await self.find_all(
            filter_dict=filter_dict,
            sort_by="created_at",
            sort_order=DESCENDING
        )
    
    @handle_db_errors
    async def get_default_resume(self, user_id: ObjectId) -> Optional[Resume]:
        """Get user's default resume."""
        return await self.find_one({
            "user_id": user_id,
            "is_default": True,
            "is_active": True
        })
    
    @handle_db_errors
    async def set_default_resume(self, resume_id: ObjectId) -> Resume:
        """Set a resume as the default for the user."""
        resume = await self.get_by_id_or_raise(resume_id)
        
        # Unset current default
        await self.model_class.find({
            "user_id": resume.user_id,
            "is_default": True
        }).update_many({"$set": {"is_default": False}})
        
        # Set new default
        resume.is_default = True
        resume.update_timestamp()
        await resume.save()
        
        return resume
    
    @handle_db_errors
    async def get_latest_resume(self, user_id: ObjectId,
                              resume_type: Optional[ResumeType] = None) -> Optional[Resume]:
        """Get the latest resume for a user."""
        filter_dict = {
            "user_id": user_id,
            "is_active": True
        }
        
        if resume_type:
            filter_dict["type"] = resume_type
        
        resumes = await self.find_all(
            filter_dict=filter_dict,
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=1
        )
        
        return resumes[0] if resumes else None
    
    @handle_db_errors
    async def find_optimized_resumes(self, user_id: ObjectId,
                                   limit: Optional[int] = None) -> List[Resume]:
        """Find all optimized resumes for a user."""
        return await self.find_by_user(
            user_id=user_id,
            resume_type=ResumeType.OPTIMIZED,
            is_active=True,
            limit=limit
        )
    
    @handle_db_errors
    async def find_original_resumes(self, user_id: ObjectId,
                                  limit: Optional[int] = None) -> List[Resume]:
        """Find all original resumes for a user."""
        return await self.find_by_user(
            user_id=user_id,
            resume_type=ResumeType.ORIGINAL,
            is_active=True,
            limit=limit
        )
    
    @handle_db_errors
    async def update_content(self, resume_id: ObjectId,
                           content: Dict[str, Any]) -> Resume:
        """Update resume content."""
        resume = await self.get_by_id_or_raise(resume_id)
        resume.content = content
        resume.update_timestamp()
        await resume.save()
        return resume
    
    @handle_db_errors
    async def update_section_content(self, resume_id: ObjectId,
                                   section_title: str,
                                   new_content: str) -> Resume:
        """Update specific section content."""
        resume = await self.get_by_id_or_raise(resume_id)
        resume.update_section_content(section_title, new_content)
        await resume.save()
        return resume
    
    @handle_db_errors
    async def add_tag(self, resume_id: ObjectId, tag: str) -> Resume:
        """Add a tag to resume."""
        resume = await self.get_by_id_or_raise(resume_id)
        resume.add_tag(tag)
        await resume.save()
        return resume
    
    @handle_db_errors
    async def remove_tag(self, resume_id: ObjectId, tag: str) -> Resume:
        """Remove a tag from resume."""
        resume = await self.get_by_id_or_raise(resume_id)
        resume.remove_tag(tag)
        await resume.save()
        return resume
    
    @handle_db_errors
    async def mark_as_used(self, resume_id: ObjectId) -> Resume:
        """Mark resume as recently used."""
        resume = await self.get_by_id_or_raise(resume_id)
        resume.mark_as_used()
        await resume.save()
        return resume
    
    @handle_db_errors
    async def deactivate_resume(self, resume_id: ObjectId) -> Resume:
        """Deactivate a resume."""
        resume = await self.get_by_id_or_raise(resume_id)
        resume.is_active = False
        resume.update_timestamp()
        await resume.save()
        return resume
    
    @handle_db_errors
    async def activate_resume(self, resume_id: ObjectId) -> Resume:
        """Activate a resume."""
        resume = await self.get_by_id_or_raise(resume_id)
        resume.is_active = True
        resume.update_timestamp()
        await resume.save()
        return resume
    
    @handle_db_errors
    async def find_by_tags(self, user_id: ObjectId, tags: List[str],
                          limit: Optional[int] = None) -> List[Resume]:
        """Find resumes by tags."""
        tags_lower = [tag.lower() for tag in tags]
        
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "tags": {"$in": tags_lower},
                "is_active": True
            },
            sort_by="last_used_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def search_resumes(self, user_id: ObjectId,
                           search_term: str,
                           limit: Optional[int] = None) -> List[Resume]:
        """Search resumes by content."""
        return await self.search_text(
            search_term=search_term,
            search_fields=["content.sections.content", "notes"],
            user_id=user_id,
            is_active=True
        )
    
    @handle_db_errors
    async def find_recently_used(self, user_id: ObjectId,
                               days: int = 30,
                               limit: Optional[int] = None) -> List[Resume]:
        """Find recently used resumes."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "last_used_at": {"$gte": cutoff_date},
                "is_active": True
            },
            sort_by="last_used_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def get_resume_statistics(self, user_id: ObjectId) -> Dict[str, Any]:
        """Get resume statistics for user."""
        # Type statistics
        type_pipeline = [
            {"$match": {
                "user_id": user_id,
                "is_active": True
            }},
            {"$group": {
                "_id": "$type",
                "count": {"$sum": 1}
            }}
        ]
        
        type_stats = await self.aggregate(type_pipeline)
        
        # Usage statistics
        usage_pipeline = [
            {"$match": {
                "user_id": user_id,
                "is_active": True
            }},
            {"$group": {
                "_id": None,
                "total_resumes": {"$sum": 1},
                "used_resumes": {
                    "$sum": {"$cond": [{"$ne": ["$last_used_at", None]}, 1, 0]}
                },
                "avg_word_count": {"$avg": {"$size": {"$split": ["$content.sections.content", " "]}}},
                "latest_created": {"$max": "$created_at"},
                "latest_used": {"$max": "$last_used_at"}
            }}
        ]
        
        usage_stats = await self.aggregate(usage_pipeline)
        usage_data = usage_stats[0] if usage_stats else {}
        
        # Get total count
        total_resumes = await self.count({
            "user_id": user_id,
            "is_active": True
        })
        
        return {
            "total_resumes": total_resumes,
            "type_breakdown": {stat["_id"]: stat["count"] for stat in type_stats},
            "used_resumes": usage_data.get("used_resumes", 0),
            "usage_rate": (usage_data.get("used_resumes", 0) / total_resumes * 100) if total_resumes > 0 else 0,
            "latest_created": usage_data.get("latest_created"),
            "latest_used": usage_data.get("latest_used")
        }
    
    @handle_db_errors
    async def find_resumes_by_format(self, user_id: ObjectId,
                                   format_type: ResumeFormat,
                                   limit: Optional[int] = None) -> List[Resume]:
        """Find resumes by file format."""
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "file_info.format": format_type,
                "is_active": True
            },
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def cleanup_old_optimized_resumes(self, user_id: ObjectId,
                                          days_to_keep: int = 90) -> int:
        """Clean up old optimized resumes."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        result = await self.delete_by_filter({
            "user_id": user_id,
            "type": ResumeType.OPTIMIZED,
            "created_at": {"$lt": cutoff_date},
            "last_used_at": None  # Only delete unused optimized resumes
        })
        
        return result
    
    async def _get_next_version(self, user_id: ObjectId, 
                              resume_type: ResumeType) -> int:
        """Get the next version number for a resume type."""
        latest_resume = await self.find_all(
            filter_dict={
                "user_id": user_id,
                "type": resume_type
            },
            sort_by="version",
            sort_order=DESCENDING,
            limit=1
        )
        
        if latest_resume:
            return latest_resume[0].version + 1
        else:
            return 1
    
    @handle_db_errors
    async def get_resume_versions(self, user_id: ObjectId,
                                resume_type: ResumeType) -> List[Resume]:
        """Get all versions of a resume type for a user."""
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "type": resume_type
            },
            sort_by="version",
            sort_order=DESCENDING
        )
    
    @handle_db_errors
    async def find_resumes_by_parent(self, parent_resume_id: ObjectId) -> List[Resume]:
        """Find resumes derived from a parent resume."""
        return await self.find_all(
            filter_dict={"parent_resume_id": parent_resume_id},
            sort_by="created_at",
            sort_order=DESCENDING
        )
# Global instance
resume_repository = ResumeRepository()