"""MCP Server implementation for Job Search Agent coordination."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Sequence
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource, 
    Tool, 
    TextContent, 
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    GetPromptRequest,
    GetPromptResult,
    ListPromptsRequest,
    ListPromptsResult,
    Prompt,
    PromptArgument
)

from app.mcp.base_agent import agent_manager
from app.config import settings


class JobSearchMCPServer:
    """MCP Server for Job Search Agent coordination."""
    
    def __init__(self):
        """Initialize the MCP server."""
        self.server = Server("job-search-agent")
        self.logger = logging.getLogger("mcp_server")
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Setup MCP server handlers."""
        
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """List available tools across all agents."""
            tools = []
            
            # Job search tools
            tools.extend([
                Tool(
                    name="search_jobs",
                    description="Search for jobs across multiple portals",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "keywords": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Job search keywords"
                            },
                            "location": {
                                "type": "string",
                                "description": "Job location"
                            },
                            "portals": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Job portals to search (linkedin, indeed, naukri)"
                            },
                            "user_id": {
                                "type": "string",
                                "description": "User ID for personalized search"
                            }
                        },
                        "required": ["keywords", "location", "user_id"]
                    }
                ),
                Tool(
                    name="get_job_details",
                    description="Get detailed information about a specific job",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "job_url": {
                                "type": "string",
                                "description": "Job posting URL"
                            },
                            "portal": {
                                "type": "string",
                                "description": "Job portal name"
                            }
                        },
                        "required": ["job_url", "portal"]
                    }
                ),
                Tool(
                    name="match_jobs",
                    description="Match jobs against user preferences and calculate scores",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User ID"
                            },
                            "job_ids": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of job IDs to match"
                            }
                        },
                        "required": ["user_id", "job_ids"]
                    }
                ),
                Tool(
                    name="queue_job_application",
                    description="Queue a job for automated application",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "User ID"
                            },
                            "job_id": {
                                "type": "string",
                                "description": "Job ID to queue"
                            },
                            "priority": {
                                "type": "integer",
                                "description": "Application priority (1-10)",
                                "minimum": 1,
                                "maximum": 10
                            }
                        },
                        "required": ["user_id", "job_id"]
                    }
                ),
                Tool(
                    name="get_agent_status",
                    description="Get status of job search agents",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "description": "Specific agent name (optional)"
                            }
                        }
                    }
                )
            ])
            
            return tools
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Handle tool calls."""
            try:
                self.logger.info(f"Tool call: {name} with args: {arguments}")
                
                if name == "search_jobs":
                    result = await self._handle_search_jobs(arguments)
                elif name == "get_job_details":
                    result = await self._handle_get_job_details(arguments)
                elif name == "match_jobs":
                    result = await self._handle_match_jobs(arguments)
                elif name == "queue_job_application":
                    result = await self._handle_queue_job_application(arguments)
                elif name == "get_agent_status":
                    result = await self._handle_get_agent_status(arguments)
                else:
                    raise ValueError(f"Unknown tool: {name}")
                
                return [TextContent(type="text", text=str(result))]
                
            except Exception as e:
                self.logger.error(f"Tool call error: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]
        
        @self.server.list_prompts()
        async def list_prompts() -> List[Prompt]:
            """List available prompts."""
            return [
                Prompt(
                    name="job_search_config",
                    description="Configure job search parameters",
                    arguments=[
                        PromptArgument(
                            name="user_preferences",
                            description="User job preferences in JSON format",
                            required=True
                        )
                    ]
                ),
                Prompt(
                    name="job_matching_criteria",
                    description="Define job matching criteria",
                    arguments=[
                        PromptArgument(
                            name="job_description",
                            description="Job description text",
                            required=True
                        ),
                        PromptArgument(
                            name="user_profile",
                            description="User profile and skills",
                            required=True
                        )
                    ]
                )
            ]
        
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: Dict[str, str]) -> GetPromptResult:
            """Handle prompt requests."""
            if name == "job_search_config":
                content = self._generate_job_search_config_prompt(arguments)
            elif name == "job_matching_criteria":
                content = self._generate_job_matching_prompt(arguments)
            else:
                raise ValueError(f"Unknown prompt: {name}")
            
            return GetPromptResult(
                description=f"Generated prompt for {name}",
                messages=[
                    {
                        "role": "user",
                        "content": TextContent(type="text", text=content)
                    }
                ]
            )
    
    async def _handle_search_jobs(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job search requests."""
        # Get job search agent
        job_search_agent = agent_manager.get_agent("job_search")
        if not job_search_agent:
            raise ValueError("Job search agent not available")
        
        # Execute job search task
        task_data = {
            "action": "search_jobs",
            "keywords": arguments["keywords"],
            "location": arguments["location"],
            "portals": arguments.get("portals", ["linkedin", "indeed", "naukri"]),
            "user_id": arguments["user_id"]
        }
        
        result = await job_search_agent.execute_task(task_data)
        return result
    
    async def _handle_get_job_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job details requests."""
        job_search_agent = agent_manager.get_agent("job_search")
        if not job_search_agent:
            raise ValueError("Job search agent not available")
        
        task_data = {
            "action": "get_job_details",
            "job_url": arguments["job_url"],
            "portal": arguments["portal"]
        }
        
        result = await job_search_agent.execute_task(task_data)
        return result
    
    async def _handle_match_jobs(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job matching requests."""
        job_search_agent = agent_manager.get_agent("job_search")
        if not job_search_agent:
            raise ValueError("Job search agent not available")
        
        task_data = {
            "action": "match_jobs",
            "user_id": arguments["user_id"],
            "job_ids": arguments["job_ids"]
        }
        
        result = await job_search_agent.execute_task(task_data)
        return result
    
    async def _handle_queue_job_application(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job application queueing."""
        job_search_agent = agent_manager.get_agent("job_search")
        if not job_search_agent:
            raise ValueError("Job search agent not available")
        
        task_data = {
            "action": "queue_application",
            "user_id": arguments["user_id"],
            "job_id": arguments["job_id"],
            "priority": arguments.get("priority", 5)
        }
        
        result = await job_search_agent.execute_task(task_data)
        return result
    
    async def _handle_get_agent_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle agent status requests."""
        agent_name = arguments.get("agent_name")
        
        if agent_name:
            status = await agent_manager.get_agent_status(agent_name)
            return {"agent": agent_name, "status": status}
        else:
            all_status = await agent_manager.get_all_agent_status()
            return {"agents": all_status}
    
    def _generate_job_search_config_prompt(self, arguments: Dict[str, str]) -> str:
        """Generate job search configuration prompt."""
        user_preferences = arguments.get("user_preferences", "{}")
        
        return f"""
Configure job search parameters based on the following user preferences:

User Preferences: {user_preferences}

Please provide a job search configuration that includes:
1. Relevant keywords and skill terms
2. Location preferences and remote work options
3. Experience level and seniority requirements
4. Industry and company type preferences
5. Salary range expectations
6. Job type preferences (full-time, contract, etc.)

Format the response as a structured configuration that can be used by the job search agent.
"""
    
    def _generate_job_matching_prompt(self, arguments: Dict[str, str]) -> str:
        """Generate job matching criteria prompt."""
        job_description = arguments.get("job_description", "")
        user_profile = arguments.get("user_profile", "")
        
        return f"""
Analyze the job match between the user profile and job description:

Job Description:
{job_description}

User Profile:
{user_profile}

Please provide a matching analysis that includes:
1. Skill alignment score (0-100)
2. Experience level match
3. Location compatibility
4. Salary range alignment
5. Key matching keywords
6. Missing requirements
7. Overall match score and recommendation

Format the response as a structured analysis for automated processing.
"""
    
    async def run(self) -> None:
        """Run the MCP server."""
        self.logger.info("Starting Job Search MCP Server")
        
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


# Server instance
mcp_server = JobSearchMCPServer()


async def start_mcp_server():
    """Start the MCP server."""
    await mcp_server.run()


if __name__ == "__main__":
    # Run the server
    asyncio.run(start_mcp_server())