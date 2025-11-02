"""Naukri job scraper implementation."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.models.job import JobPortal
from app.mcp.scrapers.base_scraper import BaseScraper, ParseError


class NaukriScraper(BaseScraper):
    """Naukri job portal scraper."""
    
    def __init__(self):
        """Initialize Naukri scraper."""
        super().__init__(
            portal=JobPortal.NAUKRI,
            base_url="https://www.naukri.com",
            rate_limit_delay=1.0,
            max_retries=3,
            timeout=30
        )
        
        # Naukri-specific headers
        self.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.naukri.com/"
        })
    
    def _build_search_url(
        self,
        keywords: List[str],
        location: str,
        experience_level: Optional[str],
        job_type: Optional[str],
        page: int
    ) -> str:
        """Build Naukri job search URL.
        
        Args:
            keywords: Search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            page: Page number
            
        Returns:
            Naukri search URL
        """
        # Join keywords with %20 (URL encoded space)
        keyword_string = "%20".join([quote_plus(kw) for kw in keywords])
        
        # Build base search URL
        base_url = "https://www.naukri.com/jobs-in-india"
        params = [
            f"k={keyword_string}",
            f"l={quote_plus(location)}",
            f"p={page}"
        ]
        
        # Add experience level filter if provided
        if experience_level:
            experience_map = {
                "entry": "0-2",
                "mid": "3-5", 
                "senior": "6-10",
                "lead": "11-15"
            }
            if experience_level.lower() in experience_map:
                params.append(f"experience={experience_map[experience_level.lower()]}")
        
        # Add job type filter if provided (Naukri doesn't have strong job type filters)
        if job_type and job_type.lower() == "remote":
            params.append("wfh=1")  # Work from home filter
        
        return f"{base_url}?{'&'.join(params)}"
    
    async def _parse_search_results(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse Naukri search results.
        
        Args:
            soup: BeautifulSoup object of the search page
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        
        try:
            # Naukri job cards have various selectors
            job_cards = (
                soup.find_all('article', {'class': re.compile(r'jobTuple')}) or
                soup.find_all('div', {'class': re.compile(r'jobTuple')}) or
                soup.find_all('div', {'class': re.compile(r'srp-jobtuple-wrapper')}) or
                soup.find_all('div', {'data-job-id': True})
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
            self.logger.error(f"Error parsing Naukri search results: {e}")
            raise ParseError(f"Failed to parse search results: {e}")
        
        return jobs
    
    def _parse_job_card(self, card: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parse individual job card from Naukri.
        
        Args:
            card: BeautifulSoup element of job card
            
        Returns:
            Job data dictionary or None if parsing fails
        """
        try:
            # Extract job title and URL
            title_element = (
                card.find('a', {'class': re.compile(r'title')}) or
                card.find('h3', {'class': re.compile(r'jobTuple-title')}) or
                card.find('a', {'class': re.compile(r'jobTuple-title')})
            )
            
            if not title_element:
                return None
            
            title = self._extract_text(title_element)
            job_url = self._make_absolute_url(self._extract_attribute(title_element, 'href'))
            
            # Extract company name
            company_element = (
                card.find('a', {'class': re.compile(r'subTitle')}) or
                card.find('div', {'class': re.compile(r'jobTuple-companyName')}) or
                card.find('span', {'class': re.compile(r'companyName')})
            )
            company = self._extract_text(company_element)
            
            # Extract experience requirement
            experience_element = (
                card.find('span', {'class': re.compile(r'experience')}) or
                card.find('div', {'class': re.compile(r'jobTuple-experience')})
            )
            experience = self._extract_text(experience_element)
            
            # Extract location
            location_element = (
                card.find('span', {'class': re.compile(r'location')}) or
                card.find('div', {'class': re.compile(r'jobTuple-location')}) or
                card.find('li', {'class': re.compile(r'location')})
            )
            location = self._extract_text(location_element)
            
            # Extract salary if available
            salary_element = (
                card.find('span', {'class': re.compile(r'salary')}) or
                card.find('div', {'class': re.compile(r'jobTuple-salary')})
            )
            salary = self._extract_text(salary_element) if salary_element else None
            
            # Extract job description snippet
            description_element = (
                card.find('div', {'class': re.compile(r'job-description')}) or
                card.find('span', {'class': re.compile(r'job-description')}) or
                card.find('ul', {'class': re.compile(r'jobTuple-skills')})
            )
            description = self._extract_text(description_element)
            
            # Extract skills/tags
            skills_elements = card.find_all('a', {'class': re.compile(r'tag')})
            skills = [self._extract_text(skill) for skill in skills_elements]
            
            # Extract posting date
            date_element = (
                card.find('span', {'class': re.compile(r'jobTuple-footerText')}) or
                card.find('div', {'class': re.compile(r'jobTuple-footerText')})
            )
            posted_date = self._extract_text(date_element)
            
            # Extract job ID
            job_id = self._extract_attribute(card, 'data-job-id')
            if not job_id:
                job_id = self._extract_job_id_from_url(job_url)
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'url': job_url,
                'portal': self.portal.value,
                'posted_date': posted_date,
                'salary': salary,
                'experience': experience,
                'skills': skills,
                'requirements': [],  # Will be filled in detailed scraping
                'external_id': job_id
            }
            
        except Exception as e:
            self.logger.warning(f"Error parsing Naukri job card: {e}")
            return None
    
    async def _parse_job_details(self, soup: BeautifulSoup, job_url: str) -> Dict[str, Any]:
        """Parse detailed job information from Naukri job page.
        
        Args:
            soup: BeautifulSoup object of the job page
            job_url: Job URL
            
        Returns:
            Detailed job information
        """
        try:
            # Extract job title
            title_element = (
                soup.find('h1', {'class': re.compile(r'jd-header-title')}) or
                soup.find('h1', {'class': re.compile(r'jobTitle')})
            )
            title = self._extract_text(title_element)
            
            # Extract company name
            company_element = (
                soup.find('a', {'class': re.compile(r'jd-header-comp-name')}) or
                soup.find('div', {'class': re.compile(r'jd-header-comp-name')})
            )
            company = self._extract_text(company_element)
            
            # Extract location
            location_element = (
                soup.find('span', {'class': re.compile(r'jd-location')}) or
                soup.find('div', {'class': re.compile(r'jd-location')})
            )
            location = self._extract_text(location_element)
            
            # Extract experience requirement
            experience_element = (
                soup.find('span', {'class': re.compile(r'jd-experience')}) or
                soup.find('div', {'class': re.compile(r'jd-experience')})
            )
            experience = self._extract_text(experience_element)
            
            # Extract salary
            salary_element = (
                soup.find('span', {'class': re.compile(r'jd-salary')}) or
                soup.find('div', {'class': re.compile(r'jd-salary')})
            )
            salary = self._extract_text(salary_element) if salary_element else None
            
            # Extract full job description
            description_element = (
                soup.find('div', {'class': re.compile(r'jd-desc')}) or
                soup.find('section', {'class': re.compile(r'jd-desc')}) or
                soup.find('div', {'class': re.compile(r'job-description')})
            )
            description = self._extract_text(description_element)
            
            # Extract requirements from description
            requirements = self._extract_requirements_from_description(description)
            
            # Extract skills
            skills_section = soup.find('div', {'class': re.compile(r'jd-skills')})
            skills = []
            if skills_section:
                skill_elements = skills_section.find_all('a') or skills_section.find_all('span')
                skills = [self._extract_text(skill) for skill in skill_elements if self._extract_text(skill)]
            
            # Extract company details
            company_details_element = soup.find('div', {'class': re.compile(r'jd-company-profile')})
            company_details = self._extract_text(company_details_element) if company_details_element else ""
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'requirements': requirements,
                'url': job_url,
                'portal': self.portal.value,
                'salary': salary,
                'experience': experience,
                'skills': skills,
                'company_details': company_details,
                'external_id': self._extract_job_id_from_url(job_url)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Naukri job details: {e}")
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
        
        # Common requirement patterns for Naukri
        requirement_patterns = [
            r'(?:require[sd]?|must have|need|should have|looking for)[:\s]*([^.]+)',
            r'(?:skills?|experience|qualifications?|expertise)[:\s]*([^.]+)',
            r'(?:responsibilities?|duties|role)[:\s]*([^.]+)',
            r'(?:minimum|preferred|desired)[:\s]*([^.]+)',
            r'(?:knowledge of|proficiency in|experience with)[:\s]*([^.]+)'
        ]
        
        for pattern in requirement_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                # Clean up and split by common separators
                items = re.split(r'[,;•\n\-\|]', match.strip())
                for item in items:
                    item = item.strip()
                    if len(item) > 3 and len(item) < 100:  # Filter reasonable length
                        requirements.append(item)
        
        # Also extract bullet points
        bullet_patterns = [
            r'[•·▪▫◦‣⁃]\s*([^•·▪▫◦‣⁃\n]+)',
            r'^\s*[-*]\s*([^-*\n]+)',
            r'^\s*\d+\.\s*([^\d\n]+)'
        ]
        
        for pattern in bullet_patterns:
            matches = re.findall(pattern, description, re.MULTILINE)
            for match in matches:
                item = match.strip()
                if len(item) > 5 and len(item) < 150:
                    requirements.append(item)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_requirements = []
        for req in requirements:
            req_lower = req.lower()
            if req_lower not in seen and len(req_lower) > 3:
                seen.add(req_lower)
                unique_requirements.append(req)
        
        return unique_requirements[:12]  # Limit to top 12 requirements
    
    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from Naukri URL.
        
        Args:
            url: Naukri job URL
            
        Returns:
            Job ID string
        """
        # Naukri job URLs typically contain job ID in various formats
        patterns = [
            r'/job-listings-([^/?]+)',
            r'/([^/]+)-jobs-([^/?]+)',
            r'jobId=([^&]+)',
            r'/([a-f0-9]{8,})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Fallback: use URL hash
        return str(hash(url))[-8:]