"""Free job search service - zero cost."""

from typing import List
from datetime import datetime
import logging

from app.utcp.free_client import FreeJobClient
from app.models.job import Job, JobPortal, CompanyInfo, JobLocation
from app.repositories.job_repository import JobRepository


logger = logging.getLogger(__name__)


class FreeJobService:
    """Optimized free job search."""
    
    def __init__(self):
        self.client = FreeJobClient()
        self.repo = JobRepository()
    
    async def search_and_save(self, user_id: str, keywords: List[str], location: str = "") -> int:
        """Search all free sources and save to DB."""
        jobs_data = await self.client.search_all(keywords, location)
        
        saved = 0
        for data in jobs_data:
            try:
                # Check if exists
                existing = await self.repo.find_by_external_id(data["id"], JobPortal.INDEED)
                if existing:
                    continue
                
                # Create job
                job = Job(
                    external_id=data["id"],
                    portal=JobPortal.INDEED,
                    url=data["url"],
                    title=data["title"],
                    company=CompanyInfo(name=data["company"]),
                    location=JobLocation(
                        city=data["location"],
                        country="Global",
                        is_remote="remote" in data["location"].lower()
                    ),
                    description=data["description"][:10000],
                    posted_date=datetime.fromisoformat(data["posted"].replace("Z", "+00:00")),
                    user_id=user_id,
                    match_score=0.0
                )
                
                await self.repo.create(job)
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save job: {e}")
        
        return saved
    
    async def close(self):
        await self.client.close()
