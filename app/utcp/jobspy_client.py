"""JobSpy client for advanced job scraping."""

from typing import List, Dict
from datetime import datetime
import asyncio


class JobSpyClient:
    """Client using JobSpy library for job scraping."""
    
    async def search_all_sources(
        self,
        keywords: List[str],
        location: str = "",
        results_wanted: int = 50
    ) -> List[Dict]:
        """Search jobs using JobSpy (LinkedIn, Indeed, ZipRecruiter, Glassdoor)."""
        try:
            from jobspy import scrape_jobs
            
            # Run in thread pool since jobspy is sync
            loop = asyncio.get_event_loop()
            jobs_df = await loop.run_in_executor(
                None,
                scrape_jobs,
                " ".join(keywords),  # search_term
                location,  # location
                results_wanted,  # results_wanted
                None,  # hours_old
                "us",  # country_indeed
                True,  # linkedin_fetch_description
                None,  # proxies
            )
            
            # Convert DataFrame to list of dicts
            jobs = []
            for _, row in jobs_df.iterrows():
                jobs.append({
                    "id": f"jobspy_{row.get('id', '')}",
                    "title": row.get('title', ''),
                    "company": row.get('company', ''),
                    "location": row.get('location', ''),
                    "url": row.get('job_url', ''),
                    "description": row.get('description', ''),
                    "posted": row.get('date_posted', datetime.now().isoformat()),
                    "source": row.get('site', 'jobspy'),
                    "salary": row.get('interval', '')
                })
            
            return jobs
        except Exception as e:
            print(f"JobSpy error: {e}")
            return []
