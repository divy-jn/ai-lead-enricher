"""
extractor.py — Enrichment pipeline orchestrator.

Ties together the crawler, preprocessor, and LLM modules into a
single pipeline: crawl → preprocess → enrich → validate.
"""

from src.schemas import CompanyEnrichment, LLMResult
from src.utils import get_logger
from src.browser import BrowserManager
from src.crawler import crawl_domain
from src.preprocessing import preprocess_page
from src.llm import enrich_with_llm

logger = get_logger(__name__)


async def enrich_domain(
    domain: str,
    browser: BrowserManager | None = None
) -> LLMResult | None:
    """Run the full enrichment pipeline for a single domain.

    Steps:
        1. Crawl relevant pages for the domain.
        2. Clean and preprocess the raw HTML.
        3. Send cleaned text to the LLM for structured extraction.
        4. Return the validated LLMResult.

    Args:
        domain: The company domain to enrich (e.g., "postman.com").
        browser: An optional reusable BrowserManager instance.

    Returns:
        An LLMResult on success, or None if the pipeline fails.
    """
    owns_browser = browser is None
    if owns_browser:
        browser = BrowserManager()
        await browser.launch()

    try:
        # Step 1: Crawl
        logger.info(f"Starting enrichment pipeline for {domain}")
        crawl_results = await crawl_domain(domain, browser)
        
        if not crawl_results:
            logger.error(f"No pages successfully crawled for {domain}")
            return None
            
        # Step 2: Preprocess
        preprocessed_pages = []
        for result in crawl_results:
            if result.page_result.success and result.page_result.html:
                page = preprocess_page(
                    url=result.page_result.final_url or result.url,
                    category=result.category,
                    raw_html=result.page_result.html,
                )
                preprocessed_pages.append(page)
                
        if not preprocessed_pages:
            logger.error(f"No pages successfully preprocessed for {domain}")
            return None
            
        # Step 3: LLM Extraction
        llm_result = await enrich_with_llm(domain, preprocessed_pages)
        return llm_result

    except Exception as e:
        logger.error(f"Enrichment pipeline failed for {domain}: {e}", exc_info=True)
        return None
        
    finally:
        if owns_browser and browser:
            await browser.close()
