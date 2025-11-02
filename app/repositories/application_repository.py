"""Application repository with application-specific operations."""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo import DESCENDING
from app.models.application import Application, ApplicationStatus, ApplicationOutcome, ApplicationAttempt, SubmissionData
from app.repositories.base import BaseRepository
from app.database_utils import handle_db_errors, NotFoundError


class ApplicationRepository(BaseRepository[Application]):
    """Repository for Application document operations."""
    
    def __init__(self):
        super().__init__(Application)
    
    @handle_db_errors
    async def create_application(self, 
                               user_id: ObjectId,
                               job_id: ObjectId,
                               resume_id: Optional[ObjectId] = None) -> Application:
        """Create a new job application."""
        # Check if application already exists for this user-job combination
        existing_app = await self.find_by_user_and_job(user_id, job_id)
        if existing_app:
            return existing_app  # Return existing application instead of creating duplicate
        
        application_data = {
            'user_id': user_id,
            'job_id': job_id,
            'resume_id': resume_id,
            'status': ApplicationStatus.PENDING
        }
        
        return await self.create(application_data)
    
    @handle_db_errors
    async def find_by_user_and_job(self, user_id: ObjectId, 
                                  job_id: ObjectId) -> Optional[Application]:
        """Find application by user and job."""
        return await self.find_one({
            "user_id": user_id,
            "job_id": job_id
        })
    
    @handle_db_errors
    async def find_by_user(self, user_id: ObjectId,
                          status: Optional[ApplicationStatus] = None,
                          limit: Optional[int] = None) -> List[Application]:
        """Find applications for a specific user."""
        filter_dict = {"user_id": user_id}
        if status:
            filter_dict["status"] = status
        
        return await self.find_all(
            filter_dict=filter_dict,
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_by_status(self, status: ApplicationStatus,
                           user_id: Optional[ObjectId] = None,
                           limit: Optional[int] = None) -> List[Application]:
        """Find applications by status."""
        filter_dict = {"status": status}
        if user_id:
            filter_dict["user_id"] = user_id
        
        return await self.find_all(
            filter_dict=filter_dict,
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_pending_applications(self, user_id: Optional[ObjectId] = None,
                                      limit: Optional[int] = None) -> List[Application]:
        """Find pending applications ready for processing."""
        return await self.find_by_status(ApplicationStatus.PENDING, user_id, limit)
    
    @handle_db_errors
    async def find_failed_applications(self, user_id: ObjectId,
                                     limit: Optional[int] = None) -> List[Application]:
        """Find failed applications that might need retry."""
        return await self.find_by_status(ApplicationStatus.FAILED, user_id, limit)
    
    @handle_db_errors
    async def find_completed_applications(self, user_id: ObjectId,
                                        limit: Optional[int] = None) -> List[Application]:
        """Find successfully completed applications."""
        return await self.find_by_status(ApplicationStatus.COMPLETED, user_id, limit)
    
    @handle_db_errors
    async def update_status(self, application_id: ObjectId, 
                          status: ApplicationStatus) -> Application:
        """Update application status."""
        application = await self.get_by_id_or_raise(application_id)
        application.status = status
        application.updated_at = datetime.utcnow()
        await application.save()
        return application
    
    @handle_db_errors
    async def add_attempt(self, application_id: ObjectId,
                         error_message: Optional[str] = None,
                         screenshots: Optional[List[str]] = None,
                         form_data: Optional[Dict[str, Any]] = None) -> Application:
        """Add a new application attempt."""
        application = await self.get_by_id_or_raise(application_id)
        application.add_attempt(error_message, screenshots, form_data)
        await application.save()
        return application
    
    @handle_db_errors
    async def complete_attempt(self, application_id: ObjectId,
                             success: bool,
                             submission_data: Optional[SubmissionData] = None,
                             error_message: Optional[str] = None) -> Application:
        """Complete the current application attempt."""
        application = await self.get_by_id_or_raise(application_id)
        application.complete_current_attempt(success, submission_data, error_message)
        await application.save()
        return application
    
    @handle_db_errors
    async def update_outcome(self, application_id: ObjectId,
                           outcome: ApplicationOutcome,
                           notes: Optional[str] = None) -> Application:
        """Update application outcome from employer."""
        application = await self.get_by_id_or_raise(application_id)
        application.update_outcome(outcome, notes)
        await application.save()
        return application
    
    @handle_db_errors
    async def find_by_outcome(self, outcome: ApplicationOutcome,
                            user_id: Optional[ObjectId] = None,
                            limit: Optional[int] = None) -> List[Application]:
        """Find applications by outcome."""
        filter_dict = {"outcome": outcome}
        if user_id:
            filter_dict["user_id"] = user_id
        
        return await self.find_all(
            filter_dict=filter_dict,
            sort_by="outcome_updated_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_recent_applications(self, user_id: ObjectId,
                                     days: int = 7,
                                     limit: Optional[int] = None) -> List[Application]:
        """Find recently created applications."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "created_at": {"$gte": cutoff_date}
            },
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def find_applications_needing_retry(self, user_id: ObjectId,
                                            max_attempts: int = 3,
                                            limit: Optional[int] = None) -> List[Application]:
        """Find failed applications that haven't exceeded max retry attempts."""
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "status": ApplicationStatus.FAILED
            }},
            {"$addFields": {
                "attempt_count": {"$size": "$attempts"}
            }},
            {"$match": {
                "attempt_count": {"$lt": max_attempts}
            }},
            {"$sort": {"created_at": -1}}
        ]
        
        if limit:
            pipeline.append({"$limit": limit})
        
        results = await self.aggregate(pipeline)
        
        # Convert results back to Application objects
        applications = []
        for result in results:
            app = Application(**result)
            applications.append(app)
        
        return applications
    
    @handle_db_errors
    async def get_application_statistics(self, user_id: ObjectId) -> Dict[str, Any]:
        """Get application statistics for user."""
        # Status statistics
        status_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        
        status_stats = await self.aggregate(status_pipeline)
        
        # Outcome statistics
        outcome_pipeline = [
            {"$match": {
                "user_id": user_id,
                "outcome": {"$ne": None}
            }},
            {"$group": {
                "_id": "$outcome",
                "count": {"$sum": 1}
            }}
        ]
        
        outcome_stats = await self.aggregate(outcome_pipeline)
        
        # Success rate calculation
        success_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total_applications": {"$sum": 1},
                "completed_applications": {
                    "$sum": {"$cond": [{"$eq": ["$status", ApplicationStatus.COMPLETED]}, 1, 0]}
                },
                "total_attempts": {"$sum": {"$size": "$attempts"}},
                "successful_attempts": {
                    "$sum": {
                        "$size": {
                            "$filter": {
                                "input": "$attempts",
                                "cond": {"$eq": ["$$this.success", True]}
                            }
                        }
                    }
                }
            }}
        ]
        
        success_stats = await self.aggregate(success_pipeline)
        success_data = success_stats[0] if success_stats else {}
        
        # Calculate rates
        total_apps = success_data.get("total_applications", 0)
        completed_apps = success_data.get("completed_applications", 0)
        total_attempts = success_data.get("total_attempts", 0)
        successful_attempts = success_data.get("successful_attempts", 0)
        
        completion_rate = (completed_apps / total_apps * 100) if total_apps > 0 else 0
        attempt_success_rate = (successful_attempts / total_attempts * 100) if total_attempts > 0 else 0
        
        return {
            "total_applications": total_apps,
            "status_breakdown": {stat["_id"]: stat["count"] for stat in status_stats},
            "outcome_breakdown": {stat["_id"]: stat["count"] for stat in outcome_stats},
            "completion_rate": round(completion_rate, 2),
            "attempt_success_rate": round(attempt_success_rate, 2),
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts
        }
    
    @handle_db_errors
    async def find_applications_by_resume(self, resume_id: ObjectId,
                                        limit: Optional[int] = None) -> List[Application]:
        """Find applications that used a specific resume."""
        return await self.find_all(
            filter_dict={"resume_id": resume_id},
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def get_application_timeline(self, user_id: ObjectId,
                                     days: int = 30) -> List[Dict[str, Any]]:
        """Get application timeline for the past N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "created_at": {"$gte": cutoff_date}
            }},
            {"$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"}
                },
                "applications_count": {"$sum": 1},
                "completed_count": {
                    "$sum": {"$cond": [{"$eq": ["$status", ApplicationStatus.COMPLETED]}, 1, 0]}
                }
            }},
            {"$sort": {"_id": 1}}
        ]
        
        return await self.aggregate(pipeline)
    
    @handle_db_errors
    async def bulk_update_status(self, application_ids: List[ObjectId],
                               status: ApplicationStatus) -> int:
        """Bulk update status for multiple applications."""
        if not application_ids:
            return 0
        
        result = await self.model_class.find(
            {"_id": {"$in": application_ids}}
        ).update_many({
            "$set": {
                "status": status,
                "updated_at": datetime.utcnow()
            }
        })
        
        return result.modified_count
    
    @handle_db_errors
    async def cleanup_old_failed_applications(self, user_id: ObjectId,
                                            days_to_keep: int = 30) -> int:
        """Clean up old failed applications."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        result = await self.delete_by_filter({
            "user_id": user_id,
            "status": ApplicationStatus.FAILED,
            "created_at": {"$lt": cutoff_date}
        })
        
        return result
    
    @handle_db_errors
    async def find_applications_with_screenshots(self, user_id: ObjectId,
                                               limit: Optional[int] = None) -> List[Application]:
        """Find applications that have screenshots."""
        return await self.find_all(
            filter_dict={
                "user_id": user_id,
                "attempts.screenshots": {"$exists": True, "$ne": []}
            },
            sort_by="created_at",
            sort_order=DESCENDING,
            limit=limit
        )
    
    @handle_db_errors
    async def get_applications_with_jobs(self, user_id: ObjectId,
                                       filters: Optional[Dict[str, Any]] = None,
                                       limit: int = 50,
                                       skip: int = 0) -> List[tuple]:
        """Get applications with their associated job data."""
        from app.models.job import Job
        
        # Build match conditions for applications
        match_conditions = {"user_id": user_id}
        
        if filters:
            if filters.get("status"):
                match_conditions["status"] = {"$in": filters["status"]}
            if filters.get("outcome"):
                match_conditions["outcome"] = {"$in": filters["outcome"]}
            if filters.get("date_from") or filters.get("date_to"):
                date_filter = {}
                if filters.get("date_from"):
                    date_filter["$gte"] = filters["date_from"]
                if filters.get("date_to"):
                    date_filter["$lte"] = filters["date_to"]
                match_conditions["created_at"] = date_filter
        
        # Aggregation pipeline to join with jobs
        pipeline = [
            {"$match": match_conditions},
            {"$lookup": {
                "from": "jobs",
                "localField": "job_id",
                "foreignField": "_id",
                "as": "job"
            }},
            {"$unwind": "$job"},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]
        
        # Add additional filters that require job data
        if filters:
            additional_match = {}
            if filters.get("portal"):
                additional_match["job.portal"] = {"$in": filters["portal"]}
            if filters.get("company"):
                additional_match["job.company.name"] = {
                    "$regex": filters["company"], "$options": "i"
                }
            if filters.get("job_title"):
                additional_match["job.title"] = {
                    "$regex": filters["job_title"], "$options": "i"
                }
            if filters.get("min_match_score") is not None:
                additional_match["job.match_score"] = {"$gte": filters["min_match_score"]}
            
            if additional_match:
                # Insert additional match after lookup
                pipeline.insert(-2, {"$match": additional_match})
        
        results = await self.aggregate(pipeline)
        
        # Convert results to Application and Job objects
        applications_with_jobs = []
        for result in results:
            job_data = result.pop("job")
            application = Application(**result)
            job = Job(**job_data)
            applications_with_jobs.append((application, job))
        
        return applications_with_jobs
    
    @handle_db_errors
    async def get_user_metrics(self, user_id: ObjectId,
                             start_date: datetime,
                             end_date: datetime) -> Dict[str, Any]:
        """Get comprehensive user metrics for dashboard."""
        # Applications by status
        status_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        status_results = await self.aggregate(status_pipeline)
        applications_by_status = {result["_id"]: result["count"] for result in status_results}
        
        # Applications by outcome
        outcome_pipeline = [
            {"$match": {
                "user_id": user_id,
                "outcome": {"$ne": None}
            }},
            {"$group": {
                "_id": "$outcome",
                "count": {"$sum": 1}
            }}
        ]
        outcome_results = await self.aggregate(outcome_pipeline)
        applications_by_outcome = {result["_id"]: result["count"] for result in outcome_results}
        
        # Applications by portal (requires job lookup)
        portal_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$lookup": {
                "from": "jobs",
                "localField": "job_id",
                "foreignField": "_id",
                "as": "job"
            }},
            {"$unwind": "$job"},
            {"$group": {
                "_id": "$job.portal",
                "count": {"$sum": 1}
            }}
        ]
        portal_results = await self.aggregate(portal_pipeline)
        applications_by_portal = {result["_id"]: result["count"] for result in portal_results}
        
        # Success and response rates
        total_applications = sum(applications_by_status.values())
        completed_applications = applications_by_status.get("completed", 0)
        success_rate = (completed_applications / total_applications * 100) if total_applications > 0 else 0.0
        
        # Response rate (applications with outcomes)
        total_with_outcomes = sum(applications_by_outcome.values())
        response_rate = (total_with_outcomes / total_applications * 100) if total_applications > 0 else 0.0
        
        # Average response time
        response_time_pipeline = [
            {"$match": {
                "user_id": user_id,
                "outcome": {"$ne": None},
                "applied_at": {"$ne": None},
                "outcome_updated_at": {"$ne": None}
            }},
            {"$project": {
                "response_time_days": {
                    "$divide": [
                        {"$subtract": ["$outcome_updated_at", "$applied_at"]},
                        1000 * 60 * 60 * 24  # Convert milliseconds to days
                    ]
                }
            }},
            {"$group": {
                "_id": None,
                "avg_response_time": {"$avg": "$response_time_days"}
            }}
        ]
        response_time_results = await self.aggregate(response_time_pipeline)
        avg_response_time = response_time_results[0]["avg_response_time"] if response_time_results else None
        
        # Applications in last 30 days
        thirty_days_ago = end_date - timedelta(days=30)
        recent_count = await self.count({
            "user_id": user_id,
            "created_at": {"$gte": thirty_days_ago}
        })
        
        # Top companies
        companies_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$lookup": {
                "from": "jobs",
                "localField": "job_id",
                "foreignField": "_id",
                "as": "job"
            }},
            {"$unwind": "$job"},
            {"$group": {
                "_id": "$job.company.name",
                "count": {"$sum": 1},
                "avg_match_score": {"$avg": "$job.match_score"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        companies_results = await self.aggregate(companies_pipeline)
        top_companies = [
            {
                "name": result["_id"],
                "applications": result["count"],
                "avg_match_score": round(result["avg_match_score"], 2)
            }
            for result in companies_results
        ]
        
        # Recent activity
        recent_activity_pipeline = [
            {"$match": {
                "user_id": user_id,
                "created_at": {"$gte": start_date}
            }},
            {"$lookup": {
                "from": "jobs",
                "localField": "job_id",
                "foreignField": "_id",
                "as": "job"
            }},
            {"$unwind": "$job"},
            {"$sort": {"created_at": -1}},
            {"$limit": 10},
            {"$project": {
                "job_title": "$job.title",
                "company": "$job.company.name",
                "status": 1,
                "outcome": 1,
                "created_at": 1,
                "applied_at": 1
            }}
        ]
        activity_results = await self.aggregate(recent_activity_pipeline)
        recent_activity = [
            {
                "job_title": result["job_title"],
                "company": result["company"],
                "status": result["status"],
                "outcome": result.get("outcome"),
                "created_at": result["created_at"],
                "applied_at": result.get("applied_at")
            }
            for result in activity_results
        ]
        
        return {
            "total_applications": total_applications,
            "applications_by_status": applications_by_status,
            "applications_by_outcome": applications_by_outcome,
            "applications_by_portal": applications_by_portal,
            "success_rate": round(success_rate, 2),
            "response_rate": round(response_rate, 2),
            "average_response_time_days": round(avg_response_time, 1) if avg_response_time else None,
            "applications_last_30_days": recent_count,
            "top_companies": top_companies,
            "recent_activity": recent_activity
        }
    
    @handle_db_errors
    async def get_application_trends(self, user_id: ObjectId, days: int) -> List[Dict[str, Any]]:
        """Get application trend data for charts."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "created_at": {"$gte": start_date}
            }},
            {"$group": {
                "_id": {
                    "year": {"$year": "$created_at"},
                    "month": {"$month": "$created_at"},
                    "day": {"$dayOfMonth": "$created_at"}
                },
                "applications_count": {"$sum": 1},
                "success_count": {
                    "$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}
                },
                "response_count": {
                    "$sum": {"$cond": [{"$ne": ["$outcome", None]}, 1, 0]}
                }
            }},
            {"$sort": {"_id": 1}},
            {"$project": {
                "date": {
                    "$dateFromParts": {
                        "year": "$_id.year",
                        "month": "$_id.month",
                        "day": "$_id.day"
                    }
                },
                "applications_count": 1,
                "success_count": 1,
                "response_count": 1
            }}
        ]
        
        return await self.aggregate(pipeline)