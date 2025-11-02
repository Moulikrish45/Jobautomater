"""Zero-cost UTCP client using only free APIs."""

import httpx
import asyncio
from typing import List, Dict
from datetime import datetime
from bs4 import BeautifulSoup
import re


class FreeJobClient:
    """Optimized client for free job APIs and scrapers."""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0, 
            limits=httpx.Limits(max_connections=20),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
    
    async def search_all(
        self, 
        keywords: List[str], 
        location: str = "",
        remote_only: bool = False,
        date_posted: str = "all",  # all, today, week, month
        job_type: str = "all",  # all, fulltime, parttime, contract
        experience: str = "all",  # all, entry, mid, senior
        salary_min: int = 0,
        sort_by: str = "relevance",  # relevance, date, company
        use_jobspy: bool = False  # Use JobSpy for better results (requires: pip install python-jobspy)
    ) -> List[Dict]:
        """Search all free sources with advanced filters."""
        tasks = [
            self._remotive(keywords),
            self._arbeitnow(keywords),
            self._findwork(keywords),
            self._weworkremotely(keywords),
            self._himalayas(keywords),
        ]
        
        # Add JobSpy for LinkedIn, Indeed, Glassdoor, ZipRecruiter
        if use_jobspy:
            tasks.append(self._jobspy_search(keywords, location))
        else:
            # Fallback to manual scraping
            tasks.extend([
                self._linkedin_jobs(keywords, location),
                self._indeed_rss(keywords, location),
                self._glassdoor(keywords, location),
            ])
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        jobs = []
        for result in results:
            if isinstance(result, list):
                jobs.extend(result)
        
        # Apply filters
        jobs = self._dedupe(jobs)
        jobs = self._filter_jobs(jobs, remote_only, date_posted, job_type, experience, salary_min)
        jobs = self._sort_jobs(jobs, sort_by, keywords)
        
        return jobs
    
    async def _jobspy_search(self, keywords: List[str], location: str) -> List[Dict]:
        """Search using JobSpy library."""
        try:
            from app.utcp.jobspy_client import JobSpyClient
            client = JobSpyClient()
            return await client.search_all_sources(keywords, location, results_wanted=100)
        except Exception as e:
            print(f"JobSpy failed: {e}")
            return []
    
    async def _remotive(self, keywords: List[str]) -> List[Dict]:
        """Remotive API - Remote jobs."""
        try:
            r = await self.client.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": " ".join(keywords), "limit": 50}
            )
            data = r.json()
            return [{
                "id": f"rem_{j['id']}",
                "title": j["title"],
                "company": j["company_name"],
                "location": "Remote",
                "url": j["url"],
                "description": j["description"],
                "posted": j["publication_date"],
                "source": "remotive"
            } for j in data.get("jobs", [])]
        except:
            return []
    
    async def _arbeitnow(self, keywords: List[str]) -> List[Dict]:
        """Arbeitnow API - EU jobs."""
        try:
            r = await self.client.get("https://www.arbeitnow.com/api/job-board-api")
            data = r.json()
            jobs = []
            for j in data.get("data", [])[:100]:
                title_desc = f"{j['title']} {j['description']}".lower()
                if any(kw.lower() in title_desc for kw in keywords):
                    jobs.append({
                        "id": f"arb_{j['slug']}",
                        "title": j["title"],
                        "company": j["company_name"],
                        "location": j["location"],
                        "url": j["url"],
                        "description": j["description"],
                        "posted": j["created_at"],
                        "source": "arbeitnow"
                    })
            return jobs[:50]
        except:
            return []
    
    async def _findwork(self, keywords: List[str]) -> List[Dict]:
        """Findwork API - Tech jobs."""
        try:
            r = await self.client.get(
                "https://findwork.dev/api/jobs/",
                params={"search": " ".join(keywords)}
            )
            data = r.json()
            return [{
                "id": f"fw_{j['id']}",
                "title": j["role"],
                "company": j["company_name"],
                "location": j["location"],
                "url": j["url"],
                "description": j["text"],
                "posted": j["date_posted"],
                "source": "findwork"
            } for j in data.get("results", [])]
        except:
            return []
    
    async def _linkedin_jobs(self, keywords: List[str], location: str) -> List[Dict]:
        """LinkedIn Jobs - Public listings."""
        try:
            query = "+".join(keywords)
            r = await self.client.get(
                f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                params={"keywords": " ".join(keywords), "location": location, "start": 0}
            )
            soup = BeautifulSoup(r.text, 'html.parser')
            jobs = []
            for card in soup.find_all('li')[:20]:
                try:
                    title_elem = card.find('h3', class_='base-search-card__title')
                    company_elem = card.find('h4', class_='base-search-card__subtitle')
                    location_elem = card.find('span', class_='job-search-card__location')
                    link_elem = card.find('a', class_='base-card__full-link')
                    
                    if title_elem and link_elem:
                        jobs.append({
                            "id": f"li_{link_elem.get('href', '').split('/')[-1][:10]}",
                            "title": title_elem.text.strip(),
                            "company": company_elem.text.strip() if company_elem else "Unknown",
                            "location": location_elem.text.strip() if location_elem else location,
                            "url": link_elem.get('href', ''),
                            "description": title_elem.text.strip(),
                            "posted": datetime.now().isoformat(),
                            "source": "linkedin"
                        })
                except:
                    continue
            return jobs
        except:
            return []
    
    async def _indeed_rss(self, keywords: List[str], location: str) -> List[Dict]:
        """Indeed RSS Feed - Public listings."""
        try:
            query = "+".join(keywords)
            r = await self.client.get(
                f"https://www.indeed.com/jobs",
                params={"q": " ".join(keywords), "l": location}
            )
            soup = BeautifulSoup(r.text, 'html.parser')
            jobs = []
            for card in soup.find_all('div', class_='job_seen_beacon')[:20]:
                try:
                    title_elem = card.find('h2', class_='jobTitle')
                    company_elem = card.find('span', class_='companyName')
                    location_elem = card.find('div', class_='companyLocation')
                    link_elem = card.find('a', href=True)
                    
                    if title_elem and link_elem:
                        jobs.append({
                            "id": f"in_{link_elem.get('data-jk', '')[:10]}",
                            "title": title_elem.text.strip(),
                            "company": company_elem.text.strip() if company_elem else "Unknown",
                            "location": location_elem.text.strip() if location_elem else location,
                            "url": f"https://www.indeed.com{link_elem['href']}",
                            "description": title_elem.text.strip(),
                            "posted": datetime.now().isoformat(),
                            "source": "indeed"
                        })
                except:
                    continue
            return jobs
        except:
            return []
    
    async def _glassdoor(self, keywords: List[str], location: str) -> List[Dict]:
        """Glassdoor - Public listings."""
        try:
            r = await self.client.get(
                "https://www.glassdoor.com/Job/jobs.htm",
                params={"sc.keyword": " ".join(keywords), "locT": "C", "locId": 1}
            )
            soup = BeautifulSoup(r.text, 'html.parser')
            jobs = []
            for card in soup.find_all('li', class_='react-job-listing')[:15]:
                try:
                    title_elem = card.find('a', class_='jobLink')
                    company_elem = card.find('div', class_='employerName')
                    if title_elem:
                        jobs.append({
                            "id": f"gd_{card.get('data-id', '')[:10]}",
                            "title": title_elem.text.strip(),
                            "company": company_elem.text.strip() if company_elem else "Unknown",
                            "location": location or "Remote",
                            "url": f"https://www.glassdoor.com{title_elem['href']}",
                            "description": title_elem.text.strip(),
                            "posted": datetime.now().isoformat(),
                            "source": "glassdoor"
                        })
                except:
                    continue
            return jobs
        except:
            return []
    
    async def _weworkremotely(self, keywords: List[str]) -> List[Dict]:
        """WeWorkRemotely - Remote jobs."""
        try:
            r = await self.client.get("https://weworkremotely.com/remote-jobs.json")
            data = r.json()
            jobs = []
            for job in data[:100]:
                title_desc = f"{job.get('title', '')} {job.get('description', '')}".lower()
                if any(kw.lower() in title_desc for kw in keywords):
                    jobs.append({
                        "id": f"wwr_{job.get('id', '')}",
                        "title": job.get('title', ''),
                        "company": job.get('company', ''),
                        "location": "Remote",
                        "url": job.get('url', ''),
                        "description": job.get('description', '')[:500],
                        "posted": datetime.now().isoformat(),
                        "source": "weworkremotely"
                    })
            return jobs[:50]
        except:
            return []
    
    async def _himalayas(self, keywords: List[str]) -> List[Dict]:
        """Himalayas - Remote jobs."""
        try:
            r = await self.client.get("https://himalayas.app/jobs/api")
            data = r.json()
            jobs = []
            for job in data.get('jobs', [])[:100]:
                title_desc = f"{job.get('title', '')} {job.get('description', '')}".lower()
                if any(kw.lower() in title_desc for kw in keywords):
                    jobs.append({
                        "id": f"him_{job.get('id', '')}",
                        "title": job.get('title', ''),
                        "company": job.get('company', {}).get('name', ''),
                        "location": job.get('location', 'Remote'),
                        "url": f"https://himalayas.app/jobs/{job.get('slug', '')}",
                        "description": job.get('description', '')[:500],
                        "posted": job.get('published_at', datetime.now().isoformat()),
                        "source": "himalayas"
                    })
            return jobs[:50]
        except:
            return []
    
    def _dedupe(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicates by title+company."""
        seen = set()
        unique = []
        for j in jobs:
            key = f"{j['title'].lower()}|{j['company'].lower()}"
            if key not in seen:
                seen.add(key)
                unique.append(j)
        return unique
    
    def _filter_jobs(
        self, 
        jobs: List[Dict], 
        remote_only: bool,
        date_posted: str,
        job_type: str,
        experience: str,
        salary_min: int
    ) -> List[Dict]:
        """Apply advanced filters."""
        filtered = []
        now = datetime.now()
        
        for job in jobs:
            # Remote filter
            if remote_only:
                loc = job.get('location', '').lower()
                if 'remote' not in loc and 'anywhere' not in loc:
                    continue
            
            # Date filter
            if date_posted != "all":
                try:
                    posted = datetime.fromisoformat(job['posted'].replace('Z', '+00:00'))
                    days_ago = (now - posted).days
                    if date_posted == "today" and days_ago > 1:
                        continue
                    if date_posted == "week" and days_ago > 7:
                        continue
                    if date_posted == "month" and days_ago > 30:
                        continue
                except:
                    pass
            
            # Job type filter
            if job_type != "all":
                title_desc = f"{job['title']} {job.get('description', '')}".lower()
                if job_type == "fulltime" and "full" not in title_desc and "full-time" not in title_desc:
                    continue
                if job_type == "parttime" and "part" not in title_desc:
                    continue
                if job_type == "contract" and "contract" not in title_desc:
                    continue
            
            # Experience filter
            if experience != "all":
                title_desc = f"{job['title']} {job.get('description', '')}".lower()
                if experience == "entry" and ("senior" in title_desc or "lead" in title_desc):
                    continue
                if experience == "senior" and ("junior" in title_desc or "entry" in title_desc):
                    continue
            
            filtered.append(job)
        
        return filtered
    
    def _sort_jobs(self, jobs: List[Dict], sort_by: str, keywords: List[str]) -> List[Dict]:
        """Sort jobs by criteria."""
        if sort_by == "date":
            return sorted(jobs, key=lambda x: x.get('posted', ''), reverse=True)
        elif sort_by == "company":
            return sorted(jobs, key=lambda x: x.get('company', ''))
        elif sort_by == "relevance":
            # Score by keyword matches
            query = ' '.join(keywords).lower()
            for job in jobs:
                score = 0
                title = job['title'].lower()
                desc = job.get('description', '').lower()
                for kw in keywords:
                    kw = kw.lower()
                    if kw in title:
                        score += 10
                    if kw in desc:
                        score += 1
                job['_score'] = score
            return sorted(jobs, key=lambda x: x.get('_score', 0), reverse=True)
        return jobs
    
    async def close(self):
        await self.client.aclose()
