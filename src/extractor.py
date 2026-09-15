"""
extractor.py — Enrichment pipeline orchestrator.

Ties together the crawler, preprocessor, and LLM modules into a
single pipeline: crawl → preprocess → enrich → validate.
"""

from src.schemas import CompanyEnrichment, LLMResult, DomainResult
from src.utils import get_logger
from src.browser import BrowserManager
from src.crawler import crawl_domain
from src.preprocessing import preprocess_page
from src.llm import enrich_with_llm

logger = get_logger(__name__)


async def enrich_domain(
    domain: str,
    browser: BrowserManager | None = None
) -> DomainResult:
    """Run the full enrichment pipeline for a single domain.

    Args:
        domain: The company domain to enrich (e.g., "postman.com").
        browser: An optional reusable BrowserManager instance.

    Returns:
        A DomainResult capturing the structured output and operational metadata.
    """
    owns_browser = browser is None
    if owns_browser:
        browser = BrowserManager()
        await browser.launch()

    result = DomainResult(
        domain=domain,
        status="failed"  # Assume failed until we succeed
    )

    try:
        # Step 1: Crawl
        logger.info(f"Starting enrichment pipeline for {domain}")
        crawl_results = await crawl_domain(domain, browser)
        
        if crawl_results:
            result.pages_crawled = len(crawl_results)
            result.pages_successful = sum(1 for r in crawl_results if r.page_result.success)
            result.pages_failed = result.pages_crawled - result.pages_successful

        if not crawl_results or result.pages_successful == 0:
            result.error = "No pages successfully crawled"
            return result
            
        # Step 2: Preprocess
        preprocessed_pages = []
        for crawl_res in crawl_results:
            if crawl_res.page_result.success and crawl_res.page_result.html:
                page = preprocess_page(
                    url=crawl_res.page_result.final_url or crawl_res.url,
                    category=crawl_res.category,
                    raw_html=crawl_res.page_result.html,
                )
                preprocessed_pages.append(page)
                
        if not preprocessed_pages:
            result.error = "No pages successfully preprocessed"
            return result
            
        # Step 3: LLM Extraction
        try:
            llm_result = await enrich_with_llm(domain, preprocessed_pages)
            result.data = llm_result.data
            result.prompt_tokens = llm_result.prompt_tokens or 0
            result.completion_tokens = llm_result.completion_tokens or 0
            result.total_tokens = llm_result.total_tokens or 0
            
            # Determine success vs partial
            if result.pages_failed > 0:
                result.status = "partial"
            else:
                result.status = "success"
                
        except Exception as e:
            logger.error(f"LLM Extraction failed for {domain}: {e}")
            result.status = "failed"
            result.error = f"LLM Error: {str(e)}"
            
        return result

    except Exception as e:
        logger.error(f"Enrichment pipeline failed for {domain}: {e}", exc_info=True)
        result.status = "failed"
        result.error = str(e)
        return result
        
    finally:
        if owns_browser and browser:
            await browser.close()


async def enrich_domains(domains: list[str]) -> list[DomainResult]:
    """Run the batch enrichment pipeline for multiple domains, reusing a single browser.

    Args:
        domains: List of domains to process.

    Returns:
        List of DomainResult objects for every domain provided.
    """
    logger.info(f"Starting batch enrichment for {len(domains)} domains.")
    results = []
    browser = BrowserManager()
    await browser.launch()

    try:
        for domain in domains:
            domain_result = await enrich_domain(domain, browser)
            results.append(domain_result)
    finally:
        await browser.close()
        
    return results
