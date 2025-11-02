"""Agent coordination layer for FastAPI backend integration."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from fastapi import HTTPException
from app.mcp.base_agent import agent_manager, BaseAgent
from app.config import settings


class AgentCoordinator:
    """Coordinates MCP agents with FastAPI backend."""
    
    def __init__(self):
        """Initialize the agent coordinator."""
        self.logger = logging.getLogger("agent_coordinator")
        self._health_check_interval = 60  # seconds
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    async def start(self) -> None:
        """Start the agent coordinator."""
        if self._is_running:
            return
        
        self.logger.info("Starting agent coordinator")
        self._is_running = True
        
        # Start all registered agents
        await agent_manager.start_all_agents()
        
        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        
        self.logger.info("Agent coordinator started successfully")
    
    async def stop(self) -> None:
        """Stop the agent coordinator."""
        if not self._is_running:
            return
        
        self.logger.info("Stopping agent coordinator")
        self._is_running = False
        
        # Cancel health check task
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        # Stop all agents
        await agent_manager.stop_all_agents()
        
        self.logger.info("Agent coordinator stopped")
    
    async def execute_agent_task(
        self, 
        agent_name: str, 
        task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a task on a specific agent.
        
        Args:
            agent_name: Name of the agent to execute task on
            task_data: Task parameters and data
            
        Returns:
            Task execution result
            
        Raises:
            HTTPException: If agent not found or task execution fails
        """
        agent = agent_manager.get_agent(agent_name)
        if not agent:
            raise HTTPException(
                status_code=404, 
                detail=f"Agent '{agent_name}' not found"
            )
        
        try:
            result = await agent.execute_task(task_data)
            return {
                "success": True,
                "agent": agent_name,
                "result": result,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Task execution failed on agent {agent_name}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Task execution failed: {str(e)}"
            )
    
    async def get_agent_status(self, agent_name: Optional[str] = None) -> Dict[str, Any]:
        """Get status of agents.
        
        Args:
            agent_name: Specific agent name (optional)
            
        Returns:
            Agent status information
        """
        if agent_name:
            status = await agent_manager.get_agent_status(agent_name)
            if not status:
                raise HTTPException(
                    status_code=404,
                    detail=f"Agent '{agent_name}' not found"
                )
            return status
        else:
            return await agent_manager.get_all_agent_status()
    
    async def restart_agent(self, agent_name: str) -> Dict[str, Any]:
        """Restart a specific agent.
        
        Args:
            agent_name: Name of the agent to restart
            
        Returns:
            Restart operation result
        """
        agent = agent_manager.get_agent(agent_name)
        if not agent:
            raise HTTPException(
                status_code=404,
                detail=f"Agent '{agent_name}' not found"
            )
        
        try:
            self.logger.info(f"Restarting agent: {agent_name}")
            await agent.stop()
            await asyncio.sleep(1)  # Brief pause
            await agent.start()
            
            return {
                "success": True,
                "agent": agent_name,
                "message": "Agent restarted successfully",
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Failed to restart agent {agent_name}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Agent restart failed: {str(e)}"
            )
    
    async def list_available_agents(self) -> List[Dict[str, Any]]:
        """List all available agents and their capabilities.
        
        Returns:
            List of agent information
        """
        agents_info = []
        
        for name, agent in agent_manager.agents.items():
            try:
                status = await agent.get_status()
                tools = await agent.list_tools()
                
                agents_info.append({
                    "name": name,
                    "description": agent.description,
                    "status": status,
                    "tools": [{"name": tool.name, "description": tool.description} for tool in tools],
                    "capabilities": await self._get_agent_capabilities(agent)
                })
            except Exception as e:
                self.logger.error(f"Error getting info for agent {name}: {e}")
                agents_info.append({
                    "name": name,
                    "description": agent.description,
                    "status": {"status": "error", "error": str(e)},
                    "tools": [],
                    "capabilities": []
                })
        
        return agents_info
    
    async def broadcast_task(
        self, 
        task_data: Dict[str, Any], 
        agent_filter: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Broadcast a task to multiple agents.
        
        Args:
            task_data: Task parameters and data
            agent_filter: List of agent names to include (optional)
            
        Returns:
            Broadcast results from all agents
        """
        results = {}
        agents_to_notify = agent_filter or list(agent_manager.agents.keys())
        
        tasks = []
        for agent_name in agents_to_notify:
            if agent_name in agent_manager.agents:
                task = self._execute_agent_task_safe(agent_name, task_data)
                tasks.append((agent_name, task))
        
        # Execute all tasks concurrently
        completed_tasks = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        for (agent_name, _), result in zip(tasks, completed_tasks):
            if isinstance(result, Exception):
                results[agent_name] = {
                    "success": False,
                    "error": str(result)
                }
            else:
                results[agent_name] = result
        
        return {
            "broadcast_id": f"broadcast_{datetime.utcnow().timestamp()}",
            "task_data": task_data,
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def _execute_agent_task_safe(
        self, 
        agent_name: str, 
        task_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Safely execute a task on an agent with error handling.
        
        Args:
            agent_name: Agent name
            task_data: Task data
            
        Returns:
            Task result or error information
        """
        try:
            return await self.execute_agent_task(agent_name, task_data)
        except Exception as e:
            return {
                "success": False,
                "agent": agent_name,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _get_agent_capabilities(self, agent: BaseAgent) -> List[str]:
        """Get agent capabilities.
        
        Args:
            agent: Agent instance
            
        Returns:
            List of capability descriptions
        """
        capabilities = []
        
        # Basic capabilities
        capabilities.append("Task execution with retry logic")
        capabilities.append("Error handling and recovery")
        capabilities.append("Status monitoring")
        
        # Agent-specific capabilities based on type
        if "job_search" in agent.name.lower():
            capabilities.extend([
                "Multi-portal job searching",
                "Job matching and scoring",
                "Duplicate detection",
                "Continuous monitoring"
            ])
        elif "resume" in agent.name.lower():
            capabilities.extend([
                "Resume optimization",
                "ATS formatting",
                "Keyword extraction",
                "PDF generation"
            ])
        elif "application" in agent.name.lower():
            capabilities.extend([
                "Browser automation",
                "Form filling",
                "File uploads",
                "Submission verification"
            ])
        
        return capabilities
    
    def is_running(self) -> bool:
        """Check if coordinator is running."""
        return self._is_running
    
    async def _health_check_loop(self) -> None:
        """Periodic health check for all agents."""
        while self._is_running:
            try:
                await asyncio.sleep(self._health_check_interval)
                
                if not self._is_running:
                    break
                
                # Check agent health
                all_status = await agent_manager.get_all_agent_status()
                
                for agent_name, status in all_status.items():
                    if status.get("status") == "error":
                        self.logger.warning(f"Agent {agent_name} is in error state: {status.get('error')}")
                        
                        # Attempt to restart failed agents
                        try:
                            await self.restart_agent(agent_name)
                            self.logger.info(f"Successfully restarted failed agent: {agent_name}")
                        except Exception as e:
                            self.logger.error(f"Failed to restart agent {agent_name}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Health check error: {e}")


# Global coordinator instance
coordinator = AgentCoordinator()