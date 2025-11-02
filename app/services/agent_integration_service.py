"""Agent integration service for coordinating MCP agents with FastAPI and Celery."""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from enum import Enum
import json

from app.config import settings
from app.mcp.coordinator import coordinator
from app.celery_app import celery_app


logger = logging.getLogger(__name__)


class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    RETRY = "retry"
    CANCELLED = "cancelled"


class AgentIntegrationService:
    """Service for integrating MCP agents with FastAPI coordination layer."""
    
    def __init__(self):
        self.active_tasks: Dict[str, Dict[str, Any]] = {}
        self.task_callbacks: Dict[str, List[Callable]] = {}
        self.agent_workflows: Dict[str, List[str]] = {}
        self._setup_workflows()
    
    def _setup_workflows(self):
        """Setup predefined agent workflows."""
        # Job application automation workflow
        self.agent_workflows["job_application"] = [
            "job_search_agent",
            "resume_builder_agent", 
            "application_agent"
        ]
        
        # Resume optimization workflow
        self.agent_workflows["resume_optimization"] = [
            "resume_builder_agent"
        ]
        
        # Job search workflow
        self.agent_workflows["job_search"] = [
            "job_search_agent"
        ]
    
    async def execute_job_search_workflow(
        self, 
        user_id: str, 
        search_criteria: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> Dict[str, Any]:
        """Execute complete job search workflow.
        
        Args:
            user_id: User identifier
            search_criteria: Job search parameters
            priority: Task priority level
            
        Returns:
            Workflow execution result
        """
        workflow_id = f"job_search_{user_id}_{datetime.utcnow().timestamp()}"
        
        try:
            logger.info(f"Starting job search workflow: {workflow_id}")
            
            # Step 1: Execute job search
            search_result = await self._execute_agent_task(
                "job_search_agent",
                {
                    "action": "search_jobs",
                    "user_id": user_id,
                    "criteria": search_criteria,
                    "workflow_id": workflow_id
                },
                priority
            )
            
            if not search_result.get("success"):
                raise Exception(f"Job search failed: {search_result.get('error')}")
            
            jobs_found = search_result.get("result", {}).get("jobs", [])
            
            return {
                "workflow_id": workflow_id,
                "success": True,
                "jobs_found": len(jobs_found),
                "jobs": jobs_found,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Job search workflow failed: {e}")
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def execute_resume_optimization_workflow(
        self,
        user_id: str,
        job_id: str,
        job_description: str,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> Dict[str, Any]:
        """Execute resume optimization workflow.
        
        Args:
            user_id: User identifier
            job_id: Job identifier
            job_description: Job description for optimization
            priority: Task priority level
            
        Returns:
            Workflow execution result
        """
        workflow_id = f"resume_opt_{user_id}_{job_id}_{datetime.utcnow().timestamp()}"
        
        try:
            logger.info(f"Starting resume optimization workflow: {workflow_id}")
            
            # Execute resume optimization
            optimization_result = await self._execute_agent_task(
                "resume_builder_agent",
                {
                    "action": "optimize_resume",
                    "user_id": user_id,
                    "job_id": job_id,
                    "job_description": job_description,
                    "workflow_id": workflow_id
                },
                priority
            )
            
            if not optimization_result.get("success"):
                raise Exception(f"Resume optimization failed: {optimization_result.get('error')}")
            
            return {
                "workflow_id": workflow_id,
                "success": True,
                "resume_path": optimization_result.get("result", {}).get("resume_path"),
                "optimization_score": optimization_result.get("result", {}).get("optimization_score"),
                "keywords_added": optimization_result.get("result", {}).get("keywords_added"),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Resume optimization workflow failed: {e}")
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def execute_application_workflow(
        self,
        user_id: str,
        job_id: str,
        resume_path: str,
        job_url: str,
        priority: TaskPriority = TaskPriority.HIGH
    ) -> Dict[str, Any]:
        """Execute job application workflow.
        
        Args:
            user_id: User identifier
            job_id: Job identifier
            resume_path: Path to optimized resume
            job_url: Job application URL
            priority: Task priority level
            
        Returns:
            Workflow execution result
        """
        workflow_id = f"application_{user_id}_{job_id}_{datetime.utcnow().timestamp()}"
        
        try:
            logger.info(f"Starting application workflow: {workflow_id}")
            
            # Execute job application
            application_result = await self._execute_agent_task(
                "application_agent",
                {
                    "action": "submit_application",
                    "user_id": user_id,
                    "job_id": job_id,
                    "resume_path": resume_path,
                    "job_url": job_url,
                    "workflow_id": workflow_id
                },
                priority
            )
            
            if not application_result.get("success"):
                raise Exception(f"Application submission failed: {application_result.get('error')}")
            
            return {
                "workflow_id": workflow_id,
                "success": True,
                "application_id": application_result.get("result", {}).get("application_id"),
                "submission_time": application_result.get("result", {}).get("submission_time"),
                "screenshots": application_result.get("result", {}).get("screenshots", []),
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Application workflow failed: {e}")
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def execute_complete_automation_workflow(
        self,
        user_id: str,
        search_criteria: Dict[str, Any],
        max_applications: int = 5,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> Dict[str, Any]:
        """Execute complete job application automation workflow.
        
        Args:
            user_id: User identifier
            search_criteria: Job search parameters
            max_applications: Maximum number of applications to submit
            priority: Task priority level
            
        Returns:
            Complete workflow execution result
        """
        workflow_id = f"complete_automation_{user_id}_{datetime.utcnow().timestamp()}"
        
        try:
            logger.info(f"Starting complete automation workflow: {workflow_id}")
            
            results = {
                "workflow_id": workflow_id,
                "user_id": user_id,
                "search_results": None,
                "applications": [],
                "success": False,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Step 1: Search for jobs
            search_result = await self.execute_job_search_workflow(
                user_id, search_criteria, priority
            )
            
            results["search_results"] = search_result
            
            if not search_result.get("success"):
                raise Exception("Job search phase failed")
            
            jobs = search_result.get("jobs", [])[:max_applications]
            
            # Step 2: Process each job (optimize resume + apply)
            for job in jobs:
                try:
                    job_id = job.get("id")
                    job_description = job.get("description", "")
                    job_url = job.get("url")
                    
                    # Optimize resume for this job
                    resume_result = await self.execute_resume_optimization_workflow(
                        user_id, job_id, job_description, priority
                    )
                    
                    if resume_result.get("success"):
                        resume_path = resume_result.get("resume_path")
                        
                        # Submit application
                        app_result = await self.execute_application_workflow(
                            user_id, job_id, resume_path, job_url, priority
                        )
                        
                        results["applications"].append({
                            "job_id": job_id,
                            "job_title": job.get("title"),
                            "company": job.get("company"),
                            "resume_optimization": resume_result,
                            "application_submission": app_result
                        })
                    else:
                        results["applications"].append({
                            "job_id": job_id,
                            "job_title": job.get("title"),
                            "company": job.get("company"),
                            "resume_optimization": resume_result,
                            "application_submission": {"success": False, "error": "Resume optimization failed"}
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing job {job.get('id')}: {e}")
                    results["applications"].append({
                        "job_id": job.get("id"),
                        "job_title": job.get("title"),
                        "company": job.get("company"),
                        "error": str(e)
                    })
            
            # Calculate success metrics
            successful_applications = sum(
                1 for app in results["applications"] 
                if app.get("application_submission", {}).get("success")
            )
            
            results["success"] = successful_applications > 0
            results["summary"] = {
                "jobs_found": len(search_result.get("jobs", [])),
                "jobs_processed": len(results["applications"]),
                "successful_applications": successful_applications,
                "success_rate": successful_applications / len(results["applications"]) if results["applications"] else 0
            }
            
            logger.info(f"Complete automation workflow completed: {workflow_id}")
            return results
            
        except Exception as e:
            logger.error(f"Complete automation workflow failed: {e}")
            return {
                "workflow_id": workflow_id,
                "success": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _execute_agent_task(
        self,
        agent_name: str,
        task_data: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> Dict[str, Any]:
        """Execute task on specific agent with enhanced error handling.
        
        Args:
            agent_name: Name of the agent
            task_data: Task parameters
            priority: Task priority level
            
        Returns:
            Task execution result
        """
        task_id = f"{agent_name}_{datetime.utcnow().timestamp()}"
        
        # Track active task
        self.active_tasks[task_id] = {
            "agent": agent_name,
            "status": TaskStatus.PENDING,
            "priority": priority,
            "started_at": datetime.utcnow(),
            "task_data": task_data
        }
        
        try:
            # Update status to running
            self.active_tasks[task_id]["status"] = TaskStatus.RUNNING
            
            # Execute task through coordinator
            result = await coordinator.execute_agent_task(agent_name, task_data)
            
            # Update status to success
            self.active_tasks[task_id]["status"] = TaskStatus.SUCCESS
            self.active_tasks[task_id]["completed_at"] = datetime.utcnow()
            self.active_tasks[task_id]["result"] = result
            
            # Execute callbacks
            await self._execute_task_callbacks(task_id, result)
            
            return result
            
        except Exception as e:
            # Update status to failure
            self.active_tasks[task_id]["status"] = TaskStatus.FAILURE
            self.active_tasks[task_id]["completed_at"] = datetime.utcnow()
            self.active_tasks[task_id]["error"] = str(e)
            
            # Execute error callbacks
            await self._execute_error_callbacks(task_id, e)
            
            raise
    
    async def schedule_celery_task(
        self,
        task_name: str,
        task_args: List[Any],
        task_kwargs: Dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        eta: Optional[datetime] = None,
        countdown: Optional[int] = None
    ) -> Dict[str, Any]:
        """Schedule a Celery task with MCP agent integration.
        
        Args:
            task_name: Celery task name
            task_args: Task arguments
            task_kwargs: Task keyword arguments
            priority: Task priority
            eta: Estimated time of arrival
            countdown: Countdown in seconds
            
        Returns:
            Task scheduling result
        """
        try:
            # Map priority to Celery priority
            celery_priority = self._map_priority_to_celery(priority)
            
            # Schedule task
            result = celery_app.send_task(
                task_name,
                args=task_args,
                kwargs=task_kwargs,
                priority=celery_priority,
                eta=eta,
                countdown=countdown
            )
            
            return {
                "success": True,
                "task_id": result.id,
                "task_name": task_name,
                "priority": priority,
                "scheduled_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to schedule Celery task {task_name}: {e}")
            return {
                "success": False,
                "error": str(e),
                "task_name": task_name
            }
    
    def _map_priority_to_celery(self, priority: TaskPriority) -> int:
        """Map TaskPriority to Celery priority number."""
        priority_map = {
            TaskPriority.LOW: 3,
            TaskPriority.NORMAL: 6,
            TaskPriority.HIGH: 9,
            TaskPriority.CRITICAL: 10
        }
        return priority_map.get(priority, 6)
    
    def add_task_callback(self, task_id: str, callback: Callable):
        """Add callback for task completion."""
        if task_id not in self.task_callbacks:
            self.task_callbacks[task_id] = []
        self.task_callbacks[task_id].append(callback)
    
    async def _execute_task_callbacks(self, task_id: str, result: Dict[str, Any]):
        """Execute callbacks for completed task."""
        callbacks = self.task_callbacks.get(task_id, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(task_id, result)
                else:
                    callback(task_id, result)
            except Exception as e:
                logger.error(f"Error executing callback for task {task_id}: {e}")
    
    async def _execute_error_callbacks(self, task_id: str, error: Exception):
        """Execute error callbacks for failed task."""
        # Implementation for error callbacks
        logger.error(f"Task {task_id} failed: {error}")
    
    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all active tasks."""
        return self.active_tasks.copy()
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get status of specific task."""
        return self.active_tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an active task."""
        if task_id in self.active_tasks:
            self.active_tasks[task_id]["status"] = TaskStatus.CANCELLED
            self.active_tasks[task_id]["cancelled_at"] = datetime.utcnow()
            return True
        return False


# Global agent integration service instance
agent_integration = AgentIntegrationService()