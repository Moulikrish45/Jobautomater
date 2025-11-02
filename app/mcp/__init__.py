"""MCP agents package for job application automation."""

from app.mcp.base_agent import BaseAgent, AgentManager, agent_manager, AgentStatus, AgentError
from app.mcp.coordinator import AgentCoordinator, coordinator
from app.mcp.server import JobSearchMCPServer, mcp_server
from app.mcp.job_search_agent import JobSearchAgent, job_search_agent
from app.mcp.resume_builder_agent import ResumeBuilderAgent, resume_builder_agent

# Register agents
agent_manager.register_agent(job_search_agent)
agent_manager.register_agent(resume_builder_agent)

__all__ = [
    "BaseAgent",
    "AgentManager", 
    "agent_manager",
    "AgentStatus",
    "AgentError",
    "AgentCoordinator",
    "coordinator",
    "JobSearchMCPServer",
    "mcp_server",
    "JobSearchAgent",
    "job_search_agent",
    "ResumeBuilderAgent",
    "resume_builder_agent"
]