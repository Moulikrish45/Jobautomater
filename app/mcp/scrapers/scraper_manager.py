"""Scraper manager for coordinating multiple job portal scrapers."""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

from app.models.job import JobPortal
from app.mcp.scrapers.base_scraper import BaseScraper, ScrapingError
from app.mcp.scrapers.linkedin_scraper import LinkedInScraper
from app.mcp.scrapers.indeed_scraper import IndeedScraper
from app.mcp.scrapers.naukri_scraper import NaukriScraper


class ScraperManager:
    """Manager for coordinating multiple job portal scrapers."""
    
    def __init__(self):
        """Initialize the scraper manager."""
        self.logger = logging.getLogger("scraper_manager")
        self.scrapers: Dict[JobPortal, BaseScraper] = {}
        self._initialize_scrapers()
        self._duplicate_tracker: Set[str] = set()
    
    def _initialize_scrapers(self) -> None:
        """Initialize all available scrapers."""
        try:
            self.scrapers[JobPortal.LINKEDIN] = LinkedInScraper()
            self.scrapers[JobPortal.INDEED] = IndeedScraper()
            self.scrapers[JobPortal.NAUKRI] = NaukriScraper()
            
            self.logger.info(f"Initialized {len(self.scrapers)} scrapers")
        except Exception as e:
            self.logger.error(f"Error initializing scrapers: {e}")
    
    async def search_all_portals(
        self,
        keywords: List[str],
        location: str,
        experience_level: Optional[str] = None,
        job_type: Optional[str] = None,
        portals: Optional[List[str]] = None,
        max_pages_per_portal: int = 3
    ) -> Dict[str, Any]:
        """Search for jobs across multiple portals.
        
        Args:
            keywords: List of search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            portals: List of portal names to search (optional)
            max_pages_per_portal: Maximum pages to scrape per portal
            
        Returns:
            Dictionary containing search results and metadata
        """
        start_time = datetime.utcnow()
        
        # Determine which portals to search
        if portals:
            selected_portals = [
                portal for portal in JobPortal 
                if portal.value in portals and portal in self.scrapers
            ]
        else:
            selected_portals = list(self.scrapers.keys())
        
        self.logger.info(f"Searching {len(selected_portals)} portals for keywords: {keywords}")
        
        # Create search tasks for each portal
        search_tasks = []
        for portal in selected_portals:
            scraper = self.scrapers[portal]
            task = self._search_portal_safe(
                scraper, keywords, location, experience_level, 
                job_type, max_pages_per_portal
            )
            search_tasks.append((portal.value, task))
        
        # Execute all searches concurrently
        results = {}
        completed_tasks = await asyncio.gather(
            *[task for _, task in search_tasks], 
            return_exceptions=True
        )
        
        # Process results
        all_jobs = []
        for (portal_name, _), result in zip(search_tasks, completed_tasks):
            if isinstance(result, Exception):
                self.logger.error(f"Search failed for {portal_name}: {result}")
                results[portal_name] = {
                    "success": False,
                    "error": str(result),
                    "jobs": []
                }
            else:
                results[portal_name] = result
                all_jobs.extend(result.get("jobs", []))
        
        # Remove cross-portal duplicates
        unique_jobs = self._remove_cross_portal_duplicates(all_jobs)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "search_metadata": {
                "keywords": keywords,
                "location": location,
                "experience_level": experience_level,
                "job_type": job_type,
                "portals_searched": [portal.value for portal in selected_portals],
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            },
            "portal_results": results,
            "summary": {
                "total_jobs_found": len(all_jobs),
                "unique_jobs": len(unique_jobs),
                "portals_successful": len([r for r in results.values() if r.get("success", False)]),
                "portals_failed": len([r for r in results.values() if not r.get("success", False)])
            },
            "jobs": unique_jobs
        }
    
    async def get_job_details(self, job_url: str, portal: str) -> Dict[str, Any]:
        """Get detailed information about a specific job.
        
        Args:
            job_url: URL of the job posting
            portal: Portal name
            
        Returns:
            Detailed job information
        """
        try:
            portal_enum = JobPortal(portal.lower())
            if portal_enum not in self.scrapers:
                raise ValueError(f"Scraper not available for portal: {portal}")
            
            scraper = self.scrapers[portal_enum]
            
            async with scraper:
                job_details = await scraper.get_job_details(job_url)
                return {
                    "success": True,
                    "job_details": job_details,
                    "portal": portal,
                    "scraped_at": datetime.utcnow().isoformat()
                }
        
        except Exception as e:
            self.logger.error(f"Error getting job details from {portal}: {e}")
            return {
                "success": False,
                "error": str(e),
                "portal": portal,
                "job_url": job_url
            }
    
    async def _search_portal_safe(
        self,
        scraper: BaseScraper,
        keywords: List[str],
        location: str,
        experience_level: Optional[str],
        job_type: Optional[str],
        max_pages: int
    ) -> Dict[str, Any]:
        """Safely search a single portal with error handling.
        
        Args:
            scraper: Portal scraper instance
            keywords: Search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            max_pages: Maximum pages to scrape
            
        Returns:
            Search results dictionary
        """
        portal_name = scraper.portal.value
        start_time = datetime.utcnow()
        
        try:
            async with scraper:
                jobs = await scraper.search_jobs(
                    keywords=keywords,
                    location=location,
                    experience_level=experience_level,
                    job_type=job_type,
                    max_pages=max_pages
                )
                
                end_time = datetime.utcnow()
                duration = (end_time - start_time).total_seconds()
                
                return {
                    "success": True,
                    "portal": portal_name,
                    "jobs": jobs,
                    "job_count": len(jobs),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "duration_seconds": duration
                }
        
        except Exception as e:
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()
            
            self.logger.error(f"Search failed for {portal_name}: {e}")
            return {
                "success": False,
                "portal": portal_name,
                "error": str(e),
                "jobs": [],
                "job_count": 0,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration
            }
    
    def _remove_cross_portal_duplicates(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs across different portals.
        
        Args:
            jobs: List of job dictionaries from all portals
            
        Returns:
            List of unique jobs
        """
        unique_jobs = []
        seen_hashes = set()
        
        for job in jobs:
            # Create hash based on title and company (more lenient than URL-based)
            title = job.get('title', '').lower().strip()
            company = job.get('company', '').lower().strip()
            location = job.get('location', '').lower().strip()
            
            # Normalize title by removing common variations
            normalized_title = self._normalize_job_title(title)
            
            job_hash = f"{normalized_title}|{company}|{location}"
            
            if job_hash not in seen_hashes:
                seen_hashes.add(job_hash)
                unique_jobs.append(job)
            else:
                self.logger.debug(f"Removed duplicate job: {title} at {company}")
        
        return unique_jobs
    
    def _normalize_job_title(self, title: str) -> str:
        """Normalize job title for better duplicate detection.
        
        Args:
            title: Original job title
            
        Returns:
            Normalized job title
        """
        if not title:
            return ""
        
        # Convert to lowercase
        normalized = title.lower()
        
        # Remove common variations and suffixes
        variations_to_remove = [
            r'\s*-\s*remote\s*',
            r'\s*\(remote\)\s*',
            r'\s*-\s*work from home\s*',
            r'\s*\(wfh\)\s*',
            r'\s*-\s*urgent\s*',
            r'\s*\(urgent\)\s*',
            r'\s*-\s*immediate joiner\s*',
            r'\s*\d+\s*years?\s*experience\s*',
            r'\s*\d+\+?\s*yrs?\s*',
        ]
        
        for pattern in variations_to_remove:
            normalized = re.sub(pattern, ' ', normalized)
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    async def get_scraper_status(self) -> Dict[str, Any]:
        """Get status of all scrapers.
        
        Returns:
            Dictionary containing scraper status information
        """
        status = {
            "scrapers": {},
            "total_scrapers": len(self.scrapers),
            "available_portals": [portal.value for portal in self.scrapers.keys()]
        }
        
        for portal, scraper in self.scrapers.items():
            try:
                # Test scraper availability with a simple check
                status["scrapers"][portal.value] = {
                    "available": True,
                    "portal": portal.value,
                    "base_url": scraper.base_url,
                    "rate_limit_delay": scraper.rate_limit_delay,
                    "max_retries": scraper.max_retries
                }
            except Exception as e:
                status["scrapers"][portal.value] = {
                    "available": False,
                    "portal": portal.value,
                    "error": str(e)
                }
        
        return status
    
    def clear_duplicate_tracker(self) -> None:
        """Clear the duplicate tracking cache."""
        self._duplicate_tracker.clear()
        self.logger.info("Cleared duplicate tracking cache")


# Global scraper manager instance
scraper_manager = ScraperManager()