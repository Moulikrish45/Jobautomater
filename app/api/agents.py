"""FastAPI endpoints for MCP agent management."""

from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.mcp.coordinator import coordinator
from app.services.agent_integration_service import agent_integration, TaskPriority


router = APIRouter(prefix="/agents", tags=["agents"])


class TaskRequest(BaseModel):
    """Request model for agent task execution."""
    task_data: Dict[str, Any]


class TaskResponse(BaseModel):
    """Response model for agent task execution."""
    success: bool
    agent: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str


class AgentStatusResponse(BaseModel):
    """Response model for agent status."""
    name: str
    description: str
    status: str
    error_count: int
    last_error: Optional[str] = None
    timestamp: str


class BroadcastRequest(BaseModel):
    """Request model for broadcasting tasks to multiple agents."""
    task_data: Dict[str, Any]
    agent_filter: Optional[List[str]] = None


class JobSearchRequest(BaseModel):
    """Request model for job search workflow."""
    user_id: str = Field(..., description="User identifier")
    search_criteria: Dict[str, Any] = Field(..., description="Job search criteria")
    priority: Optional[TaskPriority] = Field(TaskPriority.NORMAL, description="Task priority")


class ResumeOptimizationRequest(BaseModel):
    """Request model for resume optimization workflow."""
    user_id: str = Field(..., description="User identifier")
    job_id: str = Field(..., description="Job identifier")
    job_description: str = Field(..., description="Job description for optimization")
    priority: Optional[TaskPriority] = Field(TaskPriority.NORMAL, description="Task priority")


class ApplicationRequest(BaseModel):
    """Request model for job application workflow."""
    user_id: str = Field(..., description="User identifier")
    job_id: str = Field(..., description="Job identifier")
    resume_path: str = Field(..., description="Path to optimized resume")
    job_url: str = Field(..., description="Job application URL")
    priority: Optional[TaskPriority] = Field(TaskPriority.HIGH, description="Task priority")


class CompleteAutomationRequest(BaseModel):
    """Request model for complete automation workflow."""
    user_id: str = Field(..., description="User identifier")
    search_criteria: Dict[str, Any] = Field(..., description="Job search criteria")
    max_applications: Optional[int] = Field(5, description="Maximum applications to submit")
    priority: Optional[TaskPriority] = Field(TaskPriority.NORMAL, description="Task priority")


@router.get("/", response_model=List[Dict[str, Any]])
async def list_agents():
    """List all available agents and their capabilities."""
    try:
        agents = await coordinator.list_available_agents()
        return agents
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list agents: {str(e)}")


@router.get("/status")
async def get_all_agent_status():
    """Get status of all agents."""
    try:
        status = await coordinator.get_agent_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")


@router.get("/{agent_name}/status", response_model=AgentStatusResponse)
async def get_agent_status(agent_name: str):
    """Get status of a specific agent."""
    try:
        status = await coordinator.get_agent_status(agent_name)
        return status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get agent status: {str(e)}")


@router.post("/{agent_name}/execute", response_model=TaskResponse)
async def execute_agent_task(agent_name: str, request: TaskRequest):
    """Execute a task on a specific agent."""
    try:
        result = await coordinator.execute_agent_task(agent_name, request.task_data)
        return TaskResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Task execution failed: {str(e)}")


@router.post("/{agent_name}/restart")
async def restart_agent(agent_name: str):
    """Restart a specific agent."""
    try:
        result = await coordinator.restart_agent(agent_name)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent restart failed: {str(e)}")


@router.post("/broadcast")
async def broadcast_task(request: BroadcastRequest):
    """Broadcast a task to multiple agents."""
    try:
        result = await coordinator.broadcast_task(
            request.task_data, 
            request.agent_filter
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Broadcast failed: {str(e)}")


@router.post("/start")
async def start_coordinator(background_tasks: BackgroundTasks):
    """Start the agent coordinator."""
    try:
        background_tasks.add_task(coordinator.start)
        return {"message": "Agent coordinator startup initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start coordinator: {str(e)}")


@router.post("/stop")
async def stop_coordinator(background_tasks: BackgroundTasks):
    """Stop the agent coordinator."""
    try:
        background_tasks.add_task(coordinator.stop)
        return {"message": "Agent coordinator shutdown initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop coordinator: {str(e)}")


# Enhanced workflow endpoints
@router.post("/workflows/job-search")
async def execute_job_search_workflow(request: JobSearchRequest):
    """Execute job search workflow."""
    try:
        result = await agent_integration.execute_job_search_workflow(
            request.user_id,
            request.search_criteria,
            request.priority
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Job search workflow failed: {str(e)}")


@router.post("/workflows/resume-optimization")
async def execute_resume_optimization_workflow(request: ResumeOptimizationRequest):
    """Execute resume optimization workflow."""
    try:
        result = await agent_integration.execute_resume_optimization_workflow(
            request.user_id,
            request.job_id,
            request.job_description,
            request.priority
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Resume optimization workflow failed: {str(e)}")


@router.post("/workflows/application")
async def execute_application_workflow(request: ApplicationRequest):
    """Execute job application workflow."""
    try:
        result = await agent_integration.execute_application_workflow(
            request.user_id,
            request.job_id,
            request.resume_path,
            request.job_url,
            request.priority
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Application workflow failed: {str(e)}")


@router.post("/workflows/complete-automation")
async def execute_complete_automation_workflow(request: CompleteAutomationRequest):
    """Execute complete job application automation workflow."""
    try:
        result = await agent_integration.execute_complete_automation_workflow(
            request.user_id,
            request.search_criteria,
            request.max_applications,
            request.priority
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Complete automation workflow failed: {str(e)}")


# Task management endpoints
@router.get("/tasks/active")
async def get_active_tasks():
    """Get all active tasks."""
    try:
        tasks = agent_integration.get_active_tasks()
        return {"active_tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active tasks: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of specific task."""
    try:
        task_status = agent_integration.get_task_status(task_id)
        if not task_status:
            raise HTTPException(status_code=404, detail="Task not found")
        return task_status
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {str(e)}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel an active task."""
    try:
        success = await agent_integration.cancel_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or cannot be cancelled")
        
        return {
            "success": True,
            "message": f"Task {task_id} cancelled successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel task: {str(e)}")


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check endpoint for agent system."""
    try:
        status = await coordinator.get_agent_status()
        
        # Count healthy agents
        healthy_count = 0
        total_count = len(status)
        
        for agent_status in status.values():
            if agent_status.get("status") in ["idle", "running"]:
                healthy_count += 1
        
        health_status = "healthy" if healthy_count == total_count else "degraded"
        if healthy_count == 0:
            health_status = "unhealthy"
        
        return {
            "status": health_status,
            "healthy_agents": healthy_count,
            "total_agents": total_count,
            "agents": status
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "healthy_agents": 0,
            "total_agents": 0,
            "agents": {}
        }