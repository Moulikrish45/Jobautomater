"""Job repository with job-specific operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import DESCENDING
from app.models.job import Job, JobStatus, JobPortal, JobType, ExperienceLevel
from app.repositories.base import BaseRepository
from app.database_utils import handle_db_errors, NotFoundError, DuplicateError


class JobRepository(BaseRepository[Job]):
    """Repository for Job document operations."""
    
    def __init__(self):
        super().__init__(Job)
    
    @handle_db_errors
    async def create_job(self, 
                        external_id: str,
                        portal: JobPortal,
                        url: str,
                        title: str,
                        company_info: Dict[str, Any],
                        location: Dict[str, Any],
                        description: str,
                        user_id: ObjectId,
                        **kwargs) -> Job:
        """Create a new job listing."""
        # Check for duplicate job (same external_id and portal)
        existing_job = await self.find_by_external_id(external_id, portal, user_id)
        if existing_job:
            raise DuplicateError(f"Job {external_id} from {portal} already exists for user")
        
        job_data = {
            'external_id': external_id,
            'portal': portal,
            'url': url,
            'title': title,
            'company': company_info,
            'location': location,
            'description': description,
            'user_id': user_id,
            **kwargs
        }
        
        return await self.create(job_data)
    
    @handle_db_errors
    async def find_by_external_id(self, external_id: str, portal: JobPortal, 
                                 user_id: ObjectId) -> Optional[Job]:
        """Find job by external ID and portal for specific user."""
        return await self.find_one({
            "external_id": external_id,
            "portal": portal,
            "user_id": user_id
        })
    
    @handle_db_errors
    async def find_by_user(self, user_id: ObjectId, 
                          status: Optional[JobStatus] = None,
                          limit: Optional[int] = None) -> List[Job]:
        """Find jobs for a specific user."""
        filter_dict = {"user_id": user_id}
        if status:
            filter_dict["status"] = status
        
        return await self.find_all(
            filter_dict=filter_dict,
            sort_by="discovered_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_by_status(self, status: JobStatus, 
                           user_id: Optional[ObjectId] = None,
                           limit: Optional[int] = None) -> List[Job]:
        """Find jobs by status."""
        filter_dict = {"status": status}
        if user_id:
            filter_dict["user_id"] = user_id
        
        return await self.find_all(
            filter_dict=filter_dict,
            sort_by="discovered_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def get_jobs_by_status(self, user_id: ObjectId, status: JobStatus,
                               limit: int = 50, skip: int = 0) -> List[Job]:
        """Get jobs by status with pagination."""
        return await self.find_all(
            filter_dict={"user_id": user_id, "status": status},
            sort_by="discovered_at",
            sort_order=DESCENDING,
            limit=limit,
            skip=skip
        )
    
    @handle_db_errors
    async def find_queued_jobs(self, user_id: Optional[ObjectId] = None,
                              limit: Optional[int] = None) -> List[Job]:
        """Find jobs queued for application."""
        return await self.find_by_status(JobStatus.QUEUED, user_id, limit)
    
    @handle_db_errors
    async def find_applied_jobs(self, user_id: ObjectId,
                               limit: Optional[int] = None) -> List[Job]:
        """Find jobs user has applied to."""
        return await self.find_by_status(JobStatus.APPLIED, user_id, limit)
    
    @handle_db_errors
    async def update_status(self, job_id: ObjectId, status: JobStatus) -> Job:
        """Update job status."""
        job = await self.get_by_id_or_raise(job_id)
        job.update_status(status)
        await job.save()
        return job
    
    @handle_db_errors
    async def update_match_score(self, job_id: ObjectId, score: float) -> Job:
        """Update job match score."""
        job = await self.get_by_id_or_raise(job_id)
        job.update_match_score(score)
        await job.save()
        return job
    
    @handle_db_errors
    async def search_jobs(self, 
                         user_id: ObjectId,
                         search_term: Optional[str] = None,
                         portal: Optional[JobPortal] = None,
                         job_type: Optional[JobType] = None,
                         experience_level: Optional[ExperienceLevel] = None,
                         location: Optional[str] = None,
                         min_match_score: Optional[float] = None,
                         limit: Optional[int] = None) -> List[Job]:
        """Search jobs with multiple filters."""
        filter_dict = {"user_id": user_id}
        
        if portal:
            filter_dict["portal"] = portal
        if job_type:
            filter_dict["job_type"] = job_type
        if experience_level:
            filter_dict["experience_level"] = experience_level
        if min_match_score is not None:
            filter_dict["match_score"] = {"$gte": min_match_score}
        if location:
            filter_dict["$or"] = [
                {"location.city": {"$regex": location, "$options": "i"}},
                {"location.state": {"$regex": location, "$options": "i"}},
                {"location.country": {"$regex": location, "$options": "i"}}
            ]
        
        if search_term:
            return await self.search_text(
                search_term=search_term,
                search_fields=["title", "description", "company.name"],
                **filter_dict
            )
        else:
            return await self.find_all(
                filter_dict=filter_dict,
                sort_by="match_score",
                sort_order=DESCENDING,
                limit=limit
            )
    
    @handle_db_errors
    async def find_high_match_jobs(self, user_id: ObjectId, 
                                  min_score: float = 0.7,
                                  limit: Optional[int] = None) -> List[Job]:
        """Find jobs with high match scores."""
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "match_score": {"$gte": min_score},
                "status": {"$in": [JobStatus.DISCOVERED, JobStatus.QUEUED]}
            },
            sort_by="match_score",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_recent_jobs(self, user_id: ObjectId,
                              days: int = 7,
                              limit: Optional[int] = None) -> List[Job]:
        """Find recently discovered jobs."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "discovered_at": {"$gte": cutoff_date}
            },
            sort_by="discovered_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_jobs_by_company(self, user_id: ObjectId, 
                                  company_name: str,
                                  limit: Optional[int] = None) -> List[Job]:
        """Find jobs from specific company."""
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "company.name": {"$regex": company_name, "$options": "i"}
            },
            sort_by="discovered_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_jobs_by_skills(self, user_id: ObjectId,
                                 skills: List[str],
                                 limit: Optional[int] = None) -> List[Job]:
        """Find jobs matching specific skills."""
        # Convert skills to lowercase for case-insensitive matching
        skills_lower = [skill.lower() for skill in skills]
        
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "skills_required": {"$in": skills_lower}
            },
            sort_by="match_score",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def get_job_statistics(self, user_id: ObjectId) -> Dict[str, Any]:
        """Get job statistics for user."""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "avg_match_score": {"$avg": "$match_score"}
            }}
        ]
        
        status_stats = await self.aggregate(pipeline)
        
        # Get portal statistics
        portal_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$portal",
                "count": {"$sum": 1}
            }}
        ]
        
        portal_stats = await self.aggregate(portal_pipeline)
        
        # Get total count
        total_jobs = await self.count({"user_id": user_id})
        
        return {
            "total_jobs": total_jobs,
            "status_breakdown": {stat["_id"]: stat["count"] for stat in status_stats},
            "portal_breakdown": {stat["_id"]: stat["count"] for stat in portal_stats},
            "average_match_scores": {stat["_id"]: stat["avg_match_score"] for stat in status_stats}
        }
    
    @handle_db_errors
    async def bulk_update_status(self, job_ids: List[ObjectId], 
                               status: JobStatus) -> int:
        """Bulk update status for multiple jobs."""
        if not job_ids:
            return 0
        
        result = await self.model_class.find(
            {"_id": {"$in": job_ids}}
        ).update_many({
            "$set": {
                "status": status,
                "last_updated": datetime.utcnow()
            }
        })
        
        return result.modified_count
    
    @handle_db_errors
    async def cleanup_old_jobs(self, user_id: ObjectId, days_to_keep: int = 30) -> int:
        """Clean up old discovered jobs that were never applied to."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        result = await self.delete_by_filter({
            "user_id": user_id,
            "status": JobStatus.DISCOVERED,
            "discovered_at": {"$lt": cutoff_date}
        })
        
        return result
    
    @handle_db_errors
    async def find_duplicate_jobs(self, user_id: ObjectId) -> List[Dict[str, Any]]:
        """Find potential duplicate jobs based on title and company."""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": {
                    "title": {"$toLower": "$title"},
                    "company": {"$toLower": "$company.name"}
                },
                "jobs": {"$push": {"id": "$_id", "portal": "$portal", "url": "$url"}},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        
        return await self.aggregate(pipeline)
    
    @handle_db_errors
    async def get_trending_companies(self, user_id: ObjectId, 
                                   days: int = 30,
                                   limit: int = 10) -> List[Dict[str, Any]]:
        """Get trending companies based on job postings."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "discovered_at": {"$gte": cutoff_date}
            }},
            {"$group": {
                "_id": "$company.name",
                "job_count": {"$sum": 1},
                "avg_match_score": {"$avg": "$match_score"},
                "latest_job": {"$max": "$discovered_at"}
            }},
            {"$sort": {"job_count": -1}},
            {"$limit": limit}
        ]
        
        return await self.aggregate(pipeline)
    
    # Synchronous methods for Celery tasks
    
    def get_by_external_id_and_portal_sync(self, external_id: str, portal: str) -> Optional[Job]:
        """Synchronous version for Celery tasks."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.find_one({"external_id": external_id, "portal": portal})
        )
    
    def get_available_jobs_for_user_sync(self, user_id: str, limit: int = 100) -> List[Job]:
        """Get jobs available for application (not yet applied to)."""
        import asyncio
        from bson import ObjectId
        return asyncio.get_event_loop().run_until_complete(
            self.find_all({
                "user_id": ObjectId(user_id),
                "status": {"$in": ["discovered", "queued"]}
            }, limit=limit)
        )
    
    def get_old_jobs_sync(self, cutoff_date: datetime, status: str = "discovered") -> List[Job]:
        """Get old jobs for cleanup."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(
            self.find_all({
                "status": status,
                "created_at": {"$lt": cutoff_date}
            })
        )