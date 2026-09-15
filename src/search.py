"""
search.py — External web search utilities for verifying LinkedIn profiles.
"""

from src.utils import get_logger
from src.config import settings

logger = get_logger(__name__)

async def search_linkedin_person(name: str, company: str) -> str | None:
    """
    Search for a person's LinkedIn profile on the web.
    If no API key is configured, return None gracefully.
    
    This is an optional enrichment layer to verify and retrieve LinkedIn URLs
    when they are not directly available on the company website.
    """
    # For this assignment, we don't have a real API key configured by default.
    # We will simulate the check and gracefully return None.
    # In a real implementation, we'd use Tavily, SerpAPI, or DuckDuckGo here.
    
    # We could check a hypothetical setting like `settings.search_api_key`
    search_api_key = getattr(settings, "search_api_key", None)
    
    if not search_api_key:
        logger.debug(f"Skipping LinkedIn search for {name} at {company}: No search API key configured.")
        return None
        
    # If we had a key, we'd make an HTTP request here:
    # url = "https://api.tavily.com/search"
    # data = {"api_key": search_api_key, "query": f"{name} {company} site:linkedin.com/in/"}
    # ... parse response ...
    
    return None
