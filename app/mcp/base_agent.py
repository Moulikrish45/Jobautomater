"""Base MCP Agent class with async functionality and error handling."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from enum import Enum

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Resource, Tool, TextContent, ImageContent


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


class AgentError(Exception):
    """Base exception for agent errors."""
    pass


class AgentCommunicationError(AgentError):
    """Exception for agent communication errors."""
    pass


class BaseAgent(ABC):
    """Base class for MCP agents with async functionality and error handling."""
    
    def __init__(
        self,
        name: str,
        description: str,
        server_params: Optional[StdioServerParameters] = None
    ):
        """Initialize the base agent.
        
        Args:
            name: Agent name
            description: Agent description
            server_params: MCP server parameters for communication
        """
        self.name = name
        self.description = description
        self.server_params = server_params
        self.status = AgentStatus.IDLE
        self.session: Optional[ClientSession] = None
        self.logger = logging.getLogger(f"agent.{name}")
        self._error_count = 0
        self._max_errors = 5
        self._last_error: Optional[Exception] = None
        
    async def start(self) -> None:
        """Start the agent and establish MCP connection."""
        try:
            self.logger.info(f"Starting agent: {self.name}")
            
            if self.server_params:
                # Initialize MCP client session
                async with stdio_client(self.server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        self.session = session
                        await self._initialize()
                        self.status = AgentStatus.RUNNING
                        self.logger.info(f"Agent {self.name} started successfully")
            else:
                # Direct initialization without MCP server
                await self._initialize()
                self.status = AgentStatus.RUNNING
                self.logger.info(f"Agent {self.name} started in direct mode")
                
        except Exception as e:
            self.status = AgentStatus.ERROR
            self._last_error = e
            self.logger.error(f"Failed to start agent {self.name}: {e}")
            raise AgentCommunicationError(f"Agent startup failed: {e}")
    
    async def stop(self) -> None:
        """Stop the agent and cleanup resources."""
        try:
            self.logger.info(f"Stopping agent: {self.name}")
            await self._cleanup()
            self.status = AgentStatus.STOPPED
            self.session = None
            self.logger.info(f"Agent {self.name} stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping agent {self.name}: {e}")
            raise
    
    async def execute_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task with error handling and retry logic.
        
        Args:
            task_data: Task parameters and data
            
        Returns:
            Task execution result
            
        Raises:
            AgentError: If task execution fails after retries
        """
        if self.status != AgentStatus.RUNNING:
            raise AgentError(f"Agent {self.name} is not running (status: {self.status})")
        
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                self.logger.info(f"Executing task (attempt {attempt + 1}/{max_retries})")
                result = await self._execute_task_impl(task_data)
                
                # Reset error count on successful execution
                self._error_count = 0
                return result
                
            except Exception as e:
                self._error_count += 1
                self._last_error = e
                self.logger.warning(f"Task execution failed (attempt {attempt + 1}): {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    # Max retries reached
                    if self._error_count >= self._max_errors:
                        self.status = AgentStatus.ERROR
                        self.logger.error(f"Agent {self.name} disabled due to too many errors")
                    
                    raise AgentError(f"Task execution failed after {max_retries} attempts: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status and health information.
        
        Returns:
            Status information dictionary
        """
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "error_count": self._error_count,
            "last_error": str(self._last_error) if self._last_error else None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def list_tools(self) -> List[Tool]:
        """List available tools for this agent.
        
        Returns:
            List of available tools
        """
        if self.session:
            try:
                response = await self.session.list_tools()
                return response.tools
            except Exception as e:
                self.logger.error(f"Failed to list tools: {e}")
                return []
        return await self._get_default_tools()
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool with the given arguments.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        if self.session:
            try:
                response = await self.session.call_tool(name, arguments)
                return response.content
            except Exception as e:
                self.logger.error(f"Failed to call tool {name}: {e}")
                raise AgentError(f"Tool call failed: {e}")
        else:
            return await self._call_tool_direct(name, arguments)
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Initialize agent-specific resources.
        
        This method should be implemented by subclasses to perform
        any agent-specific initialization.
        """
        pass
    
    @abstractmethod
    async def _cleanup(self) -> None:
        """Cleanup agent-specific resources.
        
        This method should be implemented by subclasses to perform
        any agent-specific cleanup.
        """
        pass
    
    @abstractmethod
    async def _execute_task_impl(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the actual task implementation.
        
        This method should be implemented by subclasses to define
        the specific task execution logic.
        
        Args:
            task_data: Task parameters and data
            
        Returns:
            Task execution result
        """
        pass
    
    async def _get_default_tools(self) -> List[Tool]:
        """Get default tools when no MCP session is available.
        
        Returns:
            List of default tools
        """
        return []
    
    async def _call_tool_direct(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call tool directly when no MCP session is available.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        raise AgentError(f"Tool {name} not available in direct mode")


class AgentManager:
    """Manager for coordinating multiple MCP agents."""
    
    def __init__(self):
        """Initialize the agent manager."""
        self.agents: Dict[str, BaseAgent] = {}
        self.logger = logging.getLogger("agent_manager")
    
    def register_agent(self, agent: BaseAgent) -> None:
        """Register an agent with the manager.
        
        Args:
            agent: Agent instance to register
        """
        self.agents[agent.name] = agent
        self.logger.info(f"Registered agent: {agent.name}")
    
    def unregister_agent(self, name: str) -> None:
        """Unregister an agent from the manager.
        
        Args:
            name: Agent name to unregister
        """
        if name in self.agents:
            del self.agents[name]
            self.logger.info(f"Unregistered agent: {name}")
    
    async def start_all_agents(self) -> None:
        """Start all registered agents."""
        self.logger.info("Starting all agents")
        
        for name, agent in self.agents.items():
            try:
                await agent.start()
            except Exception as e:
                self.logger.error(f"Failed to start agent {name}: {e}")
    
    async def stop_all_agents(self) -> None:
        """Stop all registered agents."""
        self.logger.info("Stopping all agents")
        
        for name, agent in self.agents.items():
            try:
                await agent.stop()
            except Exception as e:
                self.logger.error(f"Failed to stop agent {name}: {e}")
    
    async def get_agent_status(self, name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific agent.
        
        Args:
            name: Agent name
            
        Returns:
            Agent status or None if not found
        """
        agent = self.agents.get(name)
        if agent:
            return await agent.get_status()
        return None
    
    async def get_all_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all agents.
        
        Returns:
            Dictionary mapping agent names to their status
        """
        status_dict = {}
        for name, agent in self.agents.items():
            try:
                status_dict[name] = await agent.get_status()
            except Exception as e:
                status_dict[name] = {
                    "name": name,
                    "status": "error",
                    "error": str(e)
                }
        return status_dict
    
    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name.
        
        Args:
            name: Agent name
            
        Returns:
            Agent instance or None if not found
        """
        return self.agents.get(name)


# Global agent manager instance
agent_manager = AgentManager()