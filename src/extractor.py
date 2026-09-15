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
        crawl_results, discovery_method, pages_discovered = await crawl_domain(domain, browser)
        
        result.discovery_method = discovery_method
        result.pages_discovered = pages_discovered
        
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
            from src.search import search_linkedin_person
            llm_result = await enrich_with_llm(domain, preprocessed_pages)
            data = llm_result.data
            
            # Deterministic email filtering
            deterministic_emails = {email.lower() for page in preprocessed_pages for email in page.emails}
            data.primary_generic_contacts = [e for e in data.primary_generic_contacts if e.lower() in deterministic_emails]
            data.other_public_contacts = [e for e in data.other_public_contacts if e.lower() in deterministic_emails]
            
            # Deduplicate case-insensitively and preserve order
            def dedup(lst):
                seen = set()
                res = []
                for x in lst:
                    if x.lower() not in seen:
                        seen.add(x.lower())
                        res.append(x)
                return res
                
            data.primary_generic_contacts = dedup(data.primary_generic_contacts)
            data.other_public_contacts = dedup(data.other_public_contacts)
            data.contact_points = dedup(data.primary_generic_contacts + data.other_public_contacts)
            
            # Source urls (deduplicated in crawl order)
            seen_urls = set()
            source_urls = []
            for p in preprocessed_pages:
                if p.url not in seen_urls:
                    seen_urls.add(p.url)
                    source_urls.append(p.url)
            data.source_urls = source_urls
            
            # Field-level source urls
            data.company_source_urls = list({p.url for p in preprocessed_pages if p.category and p.category.lower() in ("about", "company", "homepage", "press")})
            data.contact_source_urls = list({p.url for p in preprocessed_pages if p.category and p.category.lower() in ("contact", "support")})
            data.leadership_source_urls = list({p.url for p in preprocessed_pages if p.category and p.category.lower() in ("leadership", "team", "founders", "management", "careers")})
            
            # External LinkedIn Verification (Bonus)
            for person in data.leadership:
                if not person.linkedin_url:
                    li_url = await search_linkedin_person(person.name, domain)
                    if li_url:
                        person.linkedin_url = li_url
            
            # Evidence-aware confidence score calculation
            # Missing an optional email or leadership page does NOT force a low score.
            conf = 0.40 if (data.company_overview and data.target_audience) else 0.0
            cats = {p.category.lower() if p.category else "" for p in preprocessed_pages}
            
            if "about" in cats or "company" in cats:
                conf += 0.20
                
            if "contact" in cats:
                conf += 0.10
            if data.contact_points:
                conf += 0.10
                
            if "leadership" in cats or "team" in cats or "founders" in cats:
                conf += 0.10
            if data.leadership and any(l.name for l in data.leadership):
                conf += 0.10
                
            # Penalties
            if result.pages_failed > 0:
                conf -= min(0.20, result.pages_failed * 0.05)
                
            data.confidence_score = round(max(0.0, min(1.0, conf)), 2)
            
            result.data = data
            result.prompt_tokens = llm_result.prompt_tokens or 0
            result.completion_tokens = llm_result.completion_tokens or 0
            result.total_tokens = llm_result.total_tokens or 0
            
            # Determine success vs partial vs failed
            if data.company_overview and data.target_audience:
                result.status = "success"
            elif result.pages_successful > 0:
                result.status = "partial"
            else:
                result.status = "failed"
                
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
