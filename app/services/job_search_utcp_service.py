"""Job search service using UTCP for API integration."""

from typing import List, Dict, Any
from datetime import datetime
import logging

from app.utcp.client import UTCPClient
from app.models.job import Job, JobPortal, CompanyInfo, JobLocation


logger = logging.getLogger(__name__)


class JobSearchUTCPService:
    """Job search service using UTCP protocol."""
    
    def __init__(self):
        self.utcp = UTCPClient()
    
    async def search_all_sources(
        self,
        keywords: List[str],
        location: str,
        max_results: int = 50
    ) -> List[Job]:
        """Search jobs from all available sources."""
        all_jobs = []
        
        # Search Adzuna
        try:
            adzuna_jobs = await self._search_adzuna(keywords, location, max_results)
            all_jobs.extend(adzuna_jobs)
        except Exception as e:
            logger.error(f"Adzuna search failed: {e}")
        
        # Search Remotive (remote jobs)
        try:
            remotive_jobs = await self._search_remotive(keywords, max_results)
            all_jobs.extend(remotive_jobs)
        except Exception as e:
            logger.error(f"Remotive search failed: {e}")
        
        return all_jobs
    
    async def _search_adzuna(
        self,
        keywords: List[str],
        location: str,
        max_results: int
    ) -> List[Job]:
        """Search jobs using Adzuna API."""
        results = await self.utcp.call_tool(
            "search_jobs_adzuna",
            country="us",
            what=" ".join(keywords),
            where=location,
            results_per_page=min(max_results, 50),
            max_days_old=30
        )
        
        jobs = []
        for result in results.get("results", []):
            job = Job(
                external_id=str(result["id"]),
                portal=JobPortal.INDEED,  # Adzuna aggregates from multiple sources
                url=result["redirect_url"],
                title=result["title"],
                company=CompanyInfo(
                    name=result["company"]["display_name"]
                ),
                location=JobLocation(
                    city=result["location"]["display_name"],
                    country="US",
                    is_remote="remote" in result["location"]["display_name"].lower()
                ),
                description=result["description"],
                posted_date=datetime.fromisoformat(result["created"].replace("Z", "+00:00")),
                match_score=0.0,
                user_id=None  # Will be set by caller
            )
            jobs.append(job)
        
        return jobs
    
    async def _search_remotive(
        self,
        keywords: List[str],
        max_results: int
    ) -> List[Job]:
        """Search remote jobs using Remotive API."""
        results = await self.utcp.call_tool(
            "search_jobs_remotive",
            search=" ".join(keywords),
            limit=max_results
        )
        
        jobs = []
        for result in results.get("jobs", []):
            job = Job(
                external_id=str(result["id"]),
                portal=JobPortal.INDEED,
                url=result["url"],
                title=result["title"],
                company=CompanyInfo(
                    name=result["company_name"],
                    logo_url=result.get("company_logo")
                ),
                location=JobLocation(
                    city="Remote",
                    country="Global",
                    is_remote=True
                ),
                description=result["description"],
                posted_date=datetime.fromisoformat(result["publication_date"]),
                match_score=0.0,
                user_id=None
            )
            jobs.append(job)
        
        return jobs
    
    async def close(self):
        """Close UTCP client."""
        await self.utcp.close()
