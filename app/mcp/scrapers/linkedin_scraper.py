"""LinkedIn job scraper implementation."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.models.job import JobPortal
from app.mcp.scrapers.base_scraper import BaseScraper, ParseError


class LinkedInScraper(BaseScraper):
    """LinkedIn job portal scraper."""
    
    def __init__(self):
        """Initialize LinkedIn scraper."""
        super().__init__(
            portal=JobPortal.LINKEDIN,
            base_url="https://www.linkedin.com",
            rate_limit_delay=2.0,  # LinkedIn is more strict
            max_retries=3,
            timeout=30
        )
        
        # LinkedIn-specific headers
        self.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        })
    
    def _build_search_url(
        self,
        keywords: List[str],
        location: str,
        experience_level: Optional[str],
        job_type: Optional[str],
        page: int
    ) -> str:
        """Build LinkedIn job search URL.
        
        Args:
            keywords: Search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            page: Page number (LinkedIn uses start parameter)
            
        Returns:
            LinkedIn search URL
        """
        # Join keywords with spaces
        keyword_string = " ".join(keywords)
        
        # Build base search URL
        base_url = "https://www.linkedin.com/jobs/search"
        params = [
            f"keywords={quote_plus(keyword_string)}",
            f"location={quote_plus(location)}",
            f"start={((page - 1) * 25)}"  # LinkedIn shows 25 jobs per page
        ]
        
        # Add experience level filter if provided
        if experience_level:
            experience_map = {
                "entry": "1",
                "associate": "2", 
                "mid": "3",
                "senior": "4",
                "director": "5",
                "executive": "6"
            }
            if experience_level.lower() in experience_map:
                params.append(f"f_E={experience_map[experience_level.lower()]}")
        
        # Add job type filter if provided
        if job_type:
            job_type_map = {
                "full-time": "F",
                "part-time": "P",
                "contract": "C",
                "temporary": "T",
                "internship": "I"
            }
            if job_type.lower() in job_type_map:
                params.append(f"f_JT={job_type_map[job_type.lower()]}")
        
        return f"{base_url}?{'&'.join(params)}"
    
    async def _parse_search_results(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse LinkedIn search results.
        
        Args:
            soup: BeautifulSoup object of the search page
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        
        try:
            # LinkedIn job cards have various selectors, try multiple
            job_cards = (
                soup.find_all('div', {'class': re.compile(r'job-search-card')}) or
                soup.find_all('div', {'class': re.compile(r'jobs-search__results-list')}) or
                soup.find_all('li', {'class': re.compile(r'result-card')}) or
                soup.find_all('div', {'data-entity-urn': re.compile(r'job')})
            )
            
            for card in job_cards:
                try:
                    job_data = self._parse_job_card(card)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    self.logger.warning(f"Error parsing job card: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error parsing LinkedIn search results: {e}")
            raise ParseError(f"Failed to parse search results: {e}")
        
        return jobs
    
    def _parse_job_card(self, card: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parse individual job card from LinkedIn.
        
        Args:
            card: BeautifulSoup element of job card
            
        Returns:
            Job data dictionary or None if parsing fails
        """
        try:
            # Extract job title
            title_element = (
                card.find('h3', {'class': re.compile(r'job-search-card__title')}) or
                card.find('a', {'class': re.compile(r'job-search-card__title-link')}) or
                card.find('h4', {'class': re.compile(r'result-card__title')})
            )
            
            if not title_element:
                return None
            
            title = self._extract_text(title_element)
            
            # Extract job URL
            url_element = (
                card.find('a', {'class': re.compile(r'job-search-card__title-link')}) or
                card.find('a', href=re.compile(r'/jobs/view/'))
            )
            
            if not url_element:
                return None
            
            job_url = self._make_absolute_url(self._extract_attribute(url_element, 'href'))
            
            # Extract company name
            company_element = (
                card.find('h4', {'class': re.compile(r'job-search-card__subtitle')}) or
                card.find('a', {'class': re.compile(r'job-search-card__subtitle-link')}) or
                card.find('h5', {'class': re.compile(r'result-card__subtitle')})
            )
            company = self._extract_text(company_element)
            
            # Extract location
            location_element = (
                card.find('span', {'class': re.compile(r'job-search-card__location')}) or
                card.find('span', {'class': re.compile(r'result-card__location')})
            )
            location = self._extract_text(location_element)
            
            # Extract job description snippet
            description_element = (
                card.find('p', {'class': re.compile(r'job-search-card__snippet')}) or
                card.find('p', {'class': re.compile(r'result-card__snippet')})
            )
            description = self._extract_text(description_element)
            
            # Extract posting date
            date_element = (
                card.find('time') or
                card.find('span', {'class': re.compile(r'job-search-card__listdate')})
            )
            posted_date = self._extract_text(date_element)
            
            # Extract salary if available
            salary_element = card.find('span', {'class': re.compile(r'salary')})
            salary = self._extract_text(salary_element) if salary_element else None
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'url': job_url,
                'portal': self.portal.value,
                'posted_date': posted_date,
                'salary': salary,
                'requirements': [],  # Will be filled in detailed scraping
                'external_id': self._extract_job_id_from_url(job_url)
            }
            
        except Exception as e:
            self.logger.warning(f"Error parsing LinkedIn job card: {e}")
            return None
    
    async def _parse_job_details(self, soup: BeautifulSoup, job_url: str) -> Dict[str, Any]:
        """Parse detailed job information from LinkedIn job page.
        
        Args:
            soup: BeautifulSoup object of the job page
            job_url: Job URL
            
        Returns:
            Detailed job information
        """
        try:
            # Extract job title
            title_element = (
                soup.find('h1', {'class': re.compile(r'top-card-layout__title')}) or
                soup.find('h1', {'class': re.compile(r'topcard__title')})
            )
            title = self._extract_text(title_element)
            
            # Extract company name
            company_element = (
                soup.find('a', {'class': re.compile(r'topcard__org-name-link')}) or
                soup.find('span', {'class': re.compile(r'topcard__flavor--black-link')})
            )
            company = self._extract_text(company_element)
            
            # Extract location
            location_element = (
                soup.find('span', {'class': re.compile(r'topcard__flavor--bullet')}) or
                soup.find('span', {'class': re.compile(r'top-card-layout__second-subline')})
            )
            location = self._extract_text(location_element)
            
            # Extract full job description
            description_element = (
                soup.find('div', {'class': re.compile(r'description__text')}) or
                soup.find('section', {'class': re.compile(r'description')})
            )
            description = self._extract_text(description_element)
            
            # Extract requirements from description
            requirements = self._extract_requirements_from_description(description)
            
            # Extract salary information
            salary_element = soup.find('span', {'class': re.compile(r'salary')})
            salary = self._extract_text(salary_element) if salary_element else None
            
            # Extract job type and seniority
            criteria_elements = soup.find_all('span', {'class': re.compile(r'description-criteria__text')})
            job_type = None
            seniority_level = None
            
            for element in criteria_elements:
                text = self._extract_text(element).lower()
                if any(jt in text for jt in ['full-time', 'part-time', 'contract', 'temporary']):
                    job_type = text
                elif any(sl in text for sl in ['entry', 'associate', 'mid', 'senior', 'director', 'executive']):
                    seniority_level = text
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'requirements': requirements,
                'url': job_url,
                'portal': self.portal.value,
                'salary': salary,
                'job_type': job_type,
                'seniority_level': seniority_level,
                'external_id': self._extract_job_id_from_url(job_url)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing LinkedIn job details: {e}")
            raise ParseError(f"Failed to parse job details: {e}")
    
    def _extract_requirements_from_description(self, description: str) -> List[str]:
        """Extract requirements from job description text.
        
        Args:
            description: Job description text
            
        Returns:
            List of extracted requirements
        """
        requirements = []
        
        if not description:
            return requirements
        
        # Common requirement patterns
        requirement_patterns = [
            r'(?:require[sd]?|must have|need|looking for)[:\s]*([^.]+)',
            r'(?:skills?|experience)[:\s]*([^.]+)',
            r'(?:qualifications?)[:\s]*([^.]+)',
            r'(?:responsibilities?)[:\s]*([^.]+)'
        ]
        
        for pattern in requirement_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                # Clean up and split by common separators
                items = re.split(r'[,;•\n]', match.strip())
                for item in items:
                    item = item.strip()
                    if len(item) > 10 and len(item) < 200:  # Filter reasonable length
                        requirements.append(item)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_requirements = []
        for req in requirements:
            if req.lower() not in seen:
                seen.add(req.lower())
                unique_requirements.append(req)
        
        return unique_requirements[:10]  # Limit to top 10 requirements
    
    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from LinkedIn URL.
        
        Args:
            url: LinkedIn job URL
            
        Returns:
            Job ID string
        """
        # LinkedIn job URLs typically contain job ID after /jobs/view/
        match = re.search(r'/jobs/view/(\d+)', url)
        if match:
            return match.group(1)
        
        # Fallback: use URL hash
        return str(hash(url))[-8:]