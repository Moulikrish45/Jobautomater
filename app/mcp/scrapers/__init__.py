"""Job portal scrapers package."""

from app.mcp.scrapers.base_scraper import BaseScraper, ScrapingError
from app.mcp.scrapers.linkedin_scraper import LinkedInScraper
from app.mcp.scrapers.indeed_scraper import IndeedScraper
from app.mcp.scrapers.naukri_scraper import NaukriScraper
from app.mcp.scrapers.scraper_manager import ScraperManager, scraper_manager

__all__ = [
    "BaseScraper",
    "ScrapingError", 
    "LinkedInScraper",
    "IndeedScraper",
    "NaukriScraper",
    "ScraperManager",
    "scraper_manager"
]