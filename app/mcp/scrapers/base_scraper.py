"""Base scraper class for job portal scraping."""

import asyncio
import hashlib
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.models.job import JobPortal


class ScrapingError(Exception):
    """Base exception for scraping errors."""
    pass


class RateLimitError(ScrapingError):
    """Exception for rate limiting errors."""
    pass


class ParseError(ScrapingError):
    """Exception for parsing errors."""
    pass


class BaseScraper(ABC):
    """Base class for job portal scrapers."""
    
    def __init__(
        self,
        portal: JobPortal,
        base_url: str,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        timeout: int = 30
    ):
        """Initialize the base scraper.
        
        Args:
            portal: Job portal enum
            base_url: Base URL for the job portal
            rate_limit_delay: Delay between requests in seconds
            max_retries: Maximum number of retries for failed requests
            timeout: Request timeout in seconds
        """
        self.portal = portal
        self.base_url = base_url
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.timeout = timeout
        
        self.logger = logging.getLogger(f"scraper.{portal.value}")
        self.session: Optional[httpx.AsyncClient] = None
        self._last_request_time = 0.0
        self._seen_jobs: Set[str] = set()  # For duplicate detection
        
        # Default headers to mimic browser requests
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_session()
    
    async def start_session(self) -> None:
        """Start the HTTP session."""
        if self.session is None:
            self.session = httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True
            )
            self.logger.info(f"Started session for {self.portal.value}")
    
    async def close_session(self) -> None:
        """Close the HTTP session."""
        if self.session:
            await self.session.aclose()
            self.session = None
            self.logger.info(f"Closed session for {self.portal.value}")
    
    async def search_jobs(
        self,
        keywords: List[str],
        location: str,
        experience_level: Optional[str] = None,
        job_type: Optional[str] = None,
        max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for jobs on the portal.
        
        Args:
            keywords: List of search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            max_pages: Maximum pages to scrape
            
        Returns:
            List of job dictionaries
        """
        if not self.session:
            await self.start_session()
        
        jobs = []
        
        try:
            for page in range(1, max_pages + 1):
                self.logger.info(f"Scraping page {page} for keywords: {keywords}")
                
                # Rate limiting
                await self._rate_limit()
                
                # Get search URL for this page
                search_url = self._build_search_url(
                    keywords, location, experience_level, job_type, page
                )
                
                # Fetch and parse page
                page_jobs = await self._scrape_search_page(search_url)
                
                if not page_jobs:
                    self.logger.info(f"No more jobs found on page {page}, stopping")
                    break
                
                jobs.extend(page_jobs)
                self.logger.info(f"Found {len(page_jobs)} jobs on page {page}")
                
        except Exception as e:
            self.logger.error(f"Error during job search: {e}")
            raise ScrapingError(f"Job search failed: {e}")
        
        # Remove duplicates
        unique_jobs = self._remove_duplicates(jobs)
        self.logger.info(f"Found {len(unique_jobs)} unique jobs out of {len(jobs)} total")
        
        return unique_jobs
    
    async def get_job_details(self, job_url: str) -> Dict[str, Any]:
        """Get detailed information about a specific job.
        
        Args:
            job_url: URL of the job posting
            
        Returns:
            Detailed job information
        """
        if not self.session:
            await self.start_session()
        
        try:
            await self._rate_limit()
            
            response = await self._make_request(job_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            job_details = await self._parse_job_details(soup, job_url)
            return job_details
            
        except Exception as e:
            self.logger.error(f"Error getting job details for {job_url}: {e}")
            raise ScrapingError(f"Failed to get job details: {e}")
    
    async def _make_request(self, url: str) -> httpx.Response:
        """Make an HTTP request with retry logic.
        
        Args:
            url: URL to request
            
        Returns:
            HTTP response
        """
        for attempt in range(self.max_retries):
            try:
                response = await self.session.get(url)
                
                if response.status_code == 429:  # Rate limited
                    wait_time = 2 ** attempt
                    self.logger.warning(f"Rate limited, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ScrapingError(f"Job not found: {url}")
                elif attempt == self.max_retries - 1:
                    raise ScrapingError(f"HTTP error after {self.max_retries} attempts: {e}")
                else:
                    await asyncio.sleep(2 ** attempt)
            
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise ScrapingError(f"Request failed after {self.max_retries} attempts: {e}")
                else:
                    await asyncio.sleep(2 ** attempt)
        
        raise ScrapingError("Max retries exceeded")
    
    async def _rate_limit(self) -> None:
        """Implement rate limiting between requests."""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)
        
        self._last_request_time = asyncio.get_event_loop().time()
    
    def _remove_duplicates(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs based on URL and title hash.
        
        Args:
            jobs: List of job dictionaries
            
        Returns:
            List of unique jobs
        """
        unique_jobs = []
        
        for job in jobs:
            # Create hash from URL and title
            job_hash = self._create_job_hash(job.get('url', ''), job.get('title', ''))
            
            if job_hash not in self._seen_jobs:
                self._seen_jobs.add(job_hash)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def _create_job_hash(self, url: str, title: str) -> str:
        """Create a hash for duplicate detection.
        
        Args:
            url: Job URL
            title: Job title
            
        Returns:
            Hash string
        """
        # Normalize URL and title for consistent hashing
        normalized_url = url.lower().strip()
        normalized_title = title.lower().strip()
        
        # Create hash from URL and title
        hash_input = f"{normalized_url}|{normalized_title}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    async def _scrape_search_page(self, url: str) -> List[Dict[str, Any]]:
        """Scrape a search results page.
        
        Args:
            url: Search page URL
            
        Returns:
            List of job dictionaries from the page
        """
        try:
            response = await self._make_request(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            jobs = await self._parse_search_results(soup)
            return jobs
            
        except Exception as e:
            self.logger.error(f"Error scraping search page {url}: {e}")
            return []
    
    @abstractmethod
    def _build_search_url(
        self,
        keywords: List[str],
        location: str,
        experience_level: Optional[str],
        job_type: Optional[str],
        page: int
    ) -> str:
        """Build search URL for the specific portal.
        
        Args:
            keywords: Search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            page: Page number
            
        Returns:
            Search URL
        """
        pass
    
    @abstractmethod
    async def _parse_search_results(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse search results from HTML.
        
        Args:
            soup: BeautifulSoup object of the search page
            
        Returns:
            List of job dictionaries
        """
        pass
    
    @abstractmethod
    async def _parse_job_details(self, soup: BeautifulSoup, job_url: str) -> Dict[str, Any]:
        """Parse detailed job information from HTML.
        
        Args:
            soup: BeautifulSoup object of the job page
            job_url: Job URL
            
        Returns:
            Detailed job information dictionary
        """
        pass
    
    def _extract_text(self, element, default: str = "") -> str:
        """Safely extract text from a BeautifulSoup element.
        
        Args:
            element: BeautifulSoup element
            default: Default value if element is None
            
        Returns:
            Extracted text or default
        """
        if element:
            return element.get_text(strip=True)
        return default
    
    def _extract_attribute(self, element, attribute: str, default: str = "") -> str:
        """Safely extract attribute from a BeautifulSoup element.
        
        Args:
            element: BeautifulSoup element
            attribute: Attribute name
            default: Default value if element is None or attribute missing
            
        Returns:
            Extracted attribute or default
        """
        if element and element.has_attr(attribute):
            return element[attribute]
        return default
    
    def _make_absolute_url(self, url: str) -> str:
        """Convert relative URL to absolute URL.
        
        Args:
            url: Relative or absolute URL
            
        Returns:
            Absolute URL
        """
        if url.startswith('http'):
            return url
        return urljoin(self.base_url, url)