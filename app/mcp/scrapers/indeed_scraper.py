"""Indeed job scraper implementation."""

import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.models.job import JobPortal
from app.mcp.scrapers.base_scraper import BaseScraper, ParseError


class IndeedScraper(BaseScraper):
    """Indeed job portal scraper."""
    
    def __init__(self):
        """Initialize Indeed scraper."""
        super().__init__(
            portal=JobPortal.INDEED,
            base_url="https://www.indeed.com",
            rate_limit_delay=1.5,
            max_retries=3,
            timeout=30
        )
        
        # Indeed-specific headers
        self.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1"
        })
    
    def _build_search_url(
        self,
        keywords: List[str],
        location: str,
        experience_level: Optional[str],
        job_type: Optional[str],
        page: int
    ) -> str:
        """Build Indeed job search URL.
        
        Args:
            keywords: Search keywords
            location: Job location
            experience_level: Experience level filter
            job_type: Job type filter
            page: Page number (Indeed uses start parameter)
            
        Returns:
            Indeed search URL
        """
        # Join keywords with spaces
        keyword_string = " ".join(keywords)
        
        # Build base search URL
        base_url = "https://www.indeed.com/jobs"
        params = [
            f"q={quote_plus(keyword_string)}",
            f"l={quote_plus(location)}",
            f"start={((page - 1) * 10)}"  # Indeed shows 10-15 jobs per page
        ]
        
        # Add experience level filter if provided
        if experience_level:
            experience_map = {
                "entry": "entry_level",
                "mid": "mid_level",
                "senior": "senior_level"
            }
            if experience_level.lower() in experience_map:
                params.append(f"explvl={experience_map[experience_level.lower()]}")
        
        # Add job type filter if provided
        if job_type:
            job_type_map = {
                "full-time": "fulltime",
                "part-time": "parttime",
                "contract": "contract",
                "temporary": "temporary",
                "internship": "internship"
            }
            if job_type.lower() in job_type_map:
                params.append(f"jt={job_type_map[job_type.lower()]}")
        
        return f"{base_url}?{'&'.join(params)}"
    
    async def _parse_search_results(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Parse Indeed search results.
        
        Args:
            soup: BeautifulSoup object of the search page
            
        Returns:
            List of job dictionaries
        """
        jobs = []
        
        try:
            # Indeed job cards have various selectors
            job_cards = (
                soup.find_all('div', {'class': re.compile(r'job_seen_beacon')}) or
                soup.find_all('div', {'class': re.compile(r'slider_container')}) or
                soup.find_all('a', {'data-jk': True}) or
                soup.find_all('div', {'data-jk': True})
            )
            
            # Also try table-based layout (older Indeed format)
            if not job_cards:
                job_cards = soup.find_all('td', {'class': re.compile(r'resultContent')})
            
            for card in job_cards:
                try:
                    job_data = self._parse_job_card(card)
                    if job_data:
                        jobs.append(job_data)
                except Exception as e:
                    self.logger.warning(f"Error parsing job card: {e}")
                    continue
            
        except Exception as e:
            self.logger.error(f"Error parsing Indeed search results: {e}")
            raise ParseError(f"Failed to parse search results: {e}")
        
        return jobs
    
    def _parse_job_card(self, card: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parse individual job card from Indeed.
        
        Args:
            card: BeautifulSoup element of job card
            
        Returns:
            Job data dictionary or None if parsing fails
        """
        try:
            # Extract job title and URL
            title_element = (
                card.find('h2', {'class': re.compile(r'jobTitle')}) or
                card.find('a', {'data-jk': True}) or
                card.find('span', {'title': True})
            )
            
            if not title_element:
                # Try to find title in nested elements
                title_element = card.find('a', href=re.compile(r'/viewjob'))
            
            if not title_element:
                return None
            
            # Get title text
            title = self._extract_text(title_element)
            if not title:
                # Title might be in title attribute
                title = self._extract_attribute(title_element, 'title')
            
            # Extract job URL
            url_element = title_element if title_element.name == 'a' else title_element.find('a')
            if not url_element:
                url_element = card.find('a', href=re.compile(r'/viewjob'))
            
            if not url_element:
                return None
            
            job_url = self._make_absolute_url(self._extract_attribute(url_element, 'href'))
            
            # Extract company name
            company_element = (
                card.find('span', {'class': re.compile(r'companyName')}) or
                card.find('a', {'class': re.compile(r'companyName')}) or
                card.find('div', {'class': re.compile(r'companyName')})
            )
            company = self._extract_text(company_element)
            
            # Extract location
            location_element = (
                card.find('div', {'class': re.compile(r'companyLocation')}) or
                card.find('span', {'class': re.compile(r'companyLocation')})
            )
            location = self._extract_text(location_element)
            
            # Extract job description snippet
            description_element = (
                card.find('div', {'class': re.compile(r'job-snippet')}) or
                card.find('span', {'class': re.compile(r'summary')}) or
                card.find('div', {'class': re.compile(r'summary')})
            )
            description = self._extract_text(description_element)
            
            # Extract salary if available
            salary_element = (
                card.find('span', {'class': re.compile(r'salary-snippet')}) or
                card.find('div', {'class': re.compile(r'salary-snippet')})
            )
            salary = self._extract_text(salary_element) if salary_element else None
            
            # Extract posting date
            date_element = (
                card.find('span', {'class': re.compile(r'date')}) or
                card.find('div', {'class': re.compile(r'date')})
            )
            posted_date = self._extract_text(date_element)
            
            # Extract job key for external ID
            job_key = self._extract_attribute(card, 'data-jk')
            if not job_key:
                job_key_element = card.find(attrs={'data-jk': True})
                if job_key_element:
                    job_key = self._extract_attribute(job_key_element, 'data-jk')
            
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
                'external_id': job_key or self._extract_job_id_from_url(job_url)
            }
            
        except Exception as e:
            self.logger.warning(f"Error parsing Indeed job card: {e}")
            return None
    
    async def _parse_job_details(self, soup: BeautifulSoup, job_url: str) -> Dict[str, Any]:
        """Parse detailed job information from Indeed job page.
        
        Args:
            soup: BeautifulSoup object of the job page
            job_url: Job URL
            
        Returns:
            Detailed job information
        """
        try:
            # Extract job title
            title_element = (
                soup.find('h1', {'class': re.compile(r'jobsearch-JobInfoHeader-title')}) or
                soup.find('h3', {'class': re.compile(r'jobsearch-JobInfoHeader-title')})
            )
            title = self._extract_text(title_element)
            
            # Extract company name
            company_element = (
                soup.find('div', {'class': re.compile(r'jobsearch-InlineCompanyRating')}) or
                soup.find('a', {'class': re.compile(r'jobsearch-CompanyInfoContainer')}) or
                soup.find('span', {'class': re.compile(r'jobsearch-JobInfoHeader-companyNameSimple')})
            )
            company = self._extract_text(company_element)
            
            # Extract location
            location_element = (
                soup.find('div', {'class': re.compile(r'jobsearch-JobInfoHeader-subtitle')}) or
                soup.find('span', {'class': re.compile(r'jobsearch-JobMetadataHeader-iconLabel')})
            )
            location = self._extract_text(location_element)
            
            # Extract full job description
            description_element = (
                soup.find('div', {'class': re.compile(r'jobsearch-jobDescriptionText')}) or
                soup.find('div', {'id': 'jobDescriptionText'})
            )
            description = self._extract_text(description_element)
            
            # Extract requirements from description
            requirements = self._extract_requirements_from_description(description)
            
            # Extract salary information
            salary_element = (
                soup.find('span', {'class': re.compile(r'jobsearch-JobMetadataHeader-item')}) or
                soup.find('div', {'class': re.compile(r'jobsearch-JobMetadataHeader-item')})
            )
            salary = None
            if salary_element:
                salary_text = self._extract_text(salary_element)
                if any(indicator in salary_text.lower() for indicator in ['$', 'hour', 'year', 'salary']):
                    salary = salary_text
            
            # Extract job type from metadata
            job_type = None
            metadata_elements = soup.find_all('span', {'class': re.compile(r'jobsearch-JobMetadataHeader-iconLabel')})
            for element in metadata_elements:
                text = self._extract_text(element).lower()
                if any(jt in text for jt in ['full-time', 'part-time', 'contract', 'temporary']):
                    job_type = text
                    break
            
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
                'external_id': self._extract_job_id_from_url(job_url)
            }
            
        except Exception as e:
            self.logger.error(f"Error parsing Indeed job details: {e}")
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
        
        # Common requirement patterns for Indeed
        requirement_patterns = [
            r'(?:require[sd]?|must have|need|seeking|looking for)[:\s]*([^.]+)',
            r'(?:skills?|experience|qualifications?)[:\s]*([^.]+)',
            r'(?:responsibilities?|duties)[:\s]*([^.]+)',
            r'(?:minimum|preferred)[:\s]*([^.]+)',
            r'(?:bachelor|master|degree)[:\s]*([^.]+)'
        ]
        
        for pattern in requirement_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for match in matches:
                # Clean up and split by common separators
                items = re.split(r'[,;•\n\-]', match.strip())
                for item in items:
                    item = item.strip()
                    if len(item) > 5 and len(item) < 150:  # Filter reasonable length
                        requirements.append(item)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_requirements = []
        for req in requirements:
            req_lower = req.lower()
            if req_lower not in seen and len(req_lower) > 5:
                seen.add(req_lower)
                unique_requirements.append(req)
        
        return unique_requirements[:10]  # Limit to top 10 requirements
    
    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract job ID from Indeed URL.
        
        Args:
            url: Indeed job URL
            
        Returns:
            Job ID string
        """
        # Indeed job URLs typically contain jk parameter
        match = re.search(r'[?&]jk=([^&]+)', url)
        if match:
            return match.group(1)
        
        # Alternative pattern for viewjob URLs
        match = re.search(r'/viewjob\?jk=([^&]+)', url)
        if match:
            return match.group(1)
        
        # Fallback: use URL hash
        return str(hash(url))[-8:]