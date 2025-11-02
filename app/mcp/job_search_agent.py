"""Job Search Agent implementation using MCP framework."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.mcp.base_agent import BaseAgent, AgentStatus
from app.mcp.scrapers.scraper_manager import scraper_manager
from app.services.job_matching_service import job_matching_service
from app.tasks.job_search_tasks import (
    search_jobs_for_user,
    calculate_match_scores_for_jobs,
    queue_jobs_for_application,
    continuous_job_search
)
from app.repositories.user_repository import UserRepository
from app.repositories.job_repository import JobRepository


class JobSearchAgent(BaseAgent):
    """MCP Agent for job searching and matching operations."""
    
    def __init__(self):
        """Initialize the Job Search Agent."""
        super().__init__(
            name="job_search",
            description="Agent for searching jobs across multiple portals and matching them to user preferences"
        )
        
        self.user_repo = UserRepository()
        self.job_repo = JobRepository()
        
        # Agent-specific configuration
        self.default_search_params = {
            'max_pages_per_portal': 3,
            'min_match_score': 0.6,
            'max_jobs_per_search': 50
        }
    
    async def _initialize(self) -> None:
        """Initialize agent-specific resources."""
        self.logger.info("Initializing Job Search Agent")
        
        # Test scraper manager availability
        try:
            scraper_status = await scraper_manager.get_scraper_status()
            available_scrapers = len([
                s for s in scraper_status['scrapers'].values() 
                if s.get('available', False)
            ])
            
            self.logger.info(f"Job Search Agent initialized with {available_scrapers} available scrapers")
            
        except Exception as e:
            self.logger.warning(f"Error checking scraper status during initialization: {e}")
    
    async def _cleanup(self) -> None:
        """Cleanup agent-specific resources."""
        self.logger.info("Cleaning up Job Search Agent resources")
        # No specific cleanup needed for this agent
    
    async def _execute_task_impl(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute job search agent tasks.
        
        Args:
            task_data: Task parameters containing action and parameters
            
        Returns:
            Task execution result
        """
        action = task_data.get('action')
        
        if action == 'search_jobs':
            return await self._handle_search_jobs(task_data)
        elif action == 'get_job_details':
            return await self._handle_get_job_details(task_data)
        elif action == 'match_jobs':
            return await self._handle_match_jobs(task_data)
        elif action == 'queue_application':
            return await self._handle_queue_application(task_data)
        elif action == 'start_continuous_search':
            return await self._handle_start_continuous_search(task_data)
        elif action == 'get_search_status':
            return await self._handle_get_search_status(task_data)
        else:
            raise ValueError(f"Unknown action: {action}")
    
    async def _handle_search_jobs(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job search requests.
        
        Args:
            task_data: Search parameters
            
        Returns:
            Search results
        """
        try:
            user_id = task_data['user_id']
            keywords = task_data.get('keywords', [])
            location = task_data.get('location', 'Remote')
            portals = task_data.get('portals', ['linkedin', 'indeed', 'naukri'])
            max_pages = task_data.get('max_pages_per_portal', self.default_search_params['max_pages_per_portal'])
            
            self.logger.info(f"Starting job search for user {user_id}")
            
            # Validate user exists
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Use user preferences if keywords not provided
            if not keywords and user.preferences:
                keywords = user.preferences.desired_roles or []
            
            if not keywords:
                raise ValueError("No search keywords provided or found in user preferences")
            
            # Perform search using scraper manager
            search_results = await scraper_manager.search_all_portals(
                keywords=keywords,
                location=location,
                portals=portals,
                max_pages_per_portal=max_pages
            )
            
            # Queue Celery task for processing and storing results
            task_result = search_jobs_for_user.delay(
                user_id=user_id,
                keywords=keywords,
                location=location,
                portals=portals,
                max_pages_per_portal=max_pages
            )
            
            return {
                'success': True,
                'search_results': search_results,
                'processing_task_id': task_result.id,
                'user_id': user_id,
                'search_parameters': {
                    'keywords': keywords,
                    'location': location,
                    'portals': portals,
                    'max_pages_per_portal': max_pages
                },
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Job search failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _handle_get_job_details(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job details requests.
        
        Args:
            task_data: Job details parameters
            
        Returns:
            Job details
        """
        try:
            job_url = task_data['job_url']
            portal = task_data['portal']
            
            self.logger.info(f"Getting job details from {portal}: {job_url}")
            
            # Get job details using scraper manager
            job_details = await scraper_manager.get_job_details(job_url, portal)
            
            return {
                'success': True,
                'job_details': job_details,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get job details: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _handle_match_jobs(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job matching requests.
        
        Args:
            task_data: Matching parameters
            
        Returns:
            Job matching results
        """
        try:
            user_id = task_data['user_id']
            job_ids = task_data['job_ids']
            
            self.logger.info(f"Calculating matches for {len(job_ids)} jobs for user {user_id}")
            
            # Queue Celery task for match calculation
            task_result = calculate_match_scores_for_jobs.delay(user_id, job_ids)
            
            return {
                'success': True,
                'user_id': user_id,
                'job_ids': job_ids,
                'processing_task_id': task_result.id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Job matching failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _handle_queue_application(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle job application queueing.
        
        Args:
            task_data: Queueing parameters
            
        Returns:
            Queueing results
        """
        try:
            user_id = task_data['user_id']
            job_id = task_data['job_id']
            priority = task_data.get('priority', 5)
            
            self.logger.info(f"Queueing job {job_id} for application by user {user_id}")
            
            # Queue Celery task for application
            task_result = queue_jobs_for_application.delay(
                user_id, [job_id], priority
            )
            
            return {
                'success': True,
                'user_id': user_id,
                'job_id': job_id,
                'priority': priority,
                'processing_task_id': task_result.id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Job queueing failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _handle_start_continuous_search(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle continuous search setup.
        
        Args:
            task_data: Continuous search parameters
            
        Returns:
            Setup results
        """
        try:
            user_id = task_data['user_id']
            
            self.logger.info(f"Starting continuous search for user {user_id}")
            
            # Validate user exists and has preferences
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            if not user.preferences:
                raise ValueError("User must set job preferences before enabling continuous search")
            
            # Queue continuous search task
            task_result = continuous_job_search.delay(user_id)
            
            return {
                'success': True,
                'user_id': user_id,
                'continuous_search_task_id': task_result.id,
                'message': 'Continuous job search started',
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to start continuous search: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _handle_get_search_status(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle search status requests.
        
        Args:
            task_data: Status request parameters
            
        Returns:
            Search status information
        """
        try:
            user_id = task_data.get('user_id')
            
            # Get scraper status
            scraper_status = await scraper_manager.get_scraper_status()
            
            # Get user-specific statistics if user_id provided
            user_stats = None
            if user_id:
                user_stats = await self.job_repo.get_job_statistics(user_id)
            
            return {
                'success': True,
                'agent_status': self.status.value,
                'scraper_status': scraper_status,
                'user_stats': user_stats,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get search status: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _get_default_tools(self) -> List[Any]:
        """Get default tools for this agent."""
        return [
            {
                'name': 'search_jobs',
                'description': 'Search for jobs across multiple portals',
                'parameters': ['user_id', 'keywords', 'location', 'portals', 'max_pages_per_portal']
            },
            {
                'name': 'get_job_details',
                'description': 'Get detailed information about a specific job',
                'parameters': ['job_url', 'portal']
            },
            {
                'name': 'match_jobs',
                'description': 'Calculate match scores for jobs against user preferences',
                'parameters': ['user_id', 'job_ids']
            },
            {
                'name': 'queue_application',
                'description': 'Queue a job for automated application',
                'parameters': ['user_id', 'job_id', 'priority']
            },
            {
                'name': 'start_continuous_search',
                'description': 'Start continuous job search for a user',
                'parameters': ['user_id']
            },
            {
                'name': 'get_search_status',
                'description': 'Get current search status and statistics',
                'parameters': ['user_id']
            }
        ]
    
    async def _call_tool_direct(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call tool directly when no MCP session is available."""
        # Map tool names to task actions
        tool_action_map = {
            'search_jobs': 'search_jobs',
            'get_job_details': 'get_job_details',
            'match_jobs': 'match_jobs',
            'queue_application': 'queue_application',
            'start_continuous_search': 'start_continuous_search',
            'get_search_status': 'get_search_status'
        }
        
        if name in tool_action_map:
            task_data = {
                'action': tool_action_map[name],
                **arguments
            }
            return await self._execute_task_impl(task_data)
        else:
            raise ValueError(f"Unknown tool: {name}")


# Create and register the job search agent
job_search_agent = JobSearchAgent()