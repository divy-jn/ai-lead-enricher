"""
main.py -- CLI entry point for the Lead Enrichment Agent.

Accepts company domains as arguments and runs the enrichment pipeline.

Usage:
    python -m src.main postman.com supabase.com vapi.ai
"""

import asyncio
import sys

from src.browser import BrowserManager
from src.crawler import crawl_domain
from src.preprocessing import preprocess_page, PreprocessedPage
from src.utils import get_logger

logger = get_logger(__name__)

DEFAULT_DOMAINS = [
    "postman.com",
    "supabase.com",
    "vapi.ai",
]


async def preprocessing_smoke_test(domains: list[str]) -> None:
    """Crawl, preprocess, and display results for each domain.

    This is a temporary smoke test for the preprocessing layer (Phase 4).
    It will be replaced by the full enrichment pipeline in later phases.
    """
    async with BrowserManager() as bm:
        for domain in domains:
            print(f"\n{'#'*64}")
            print(f"#  DOMAIN: {domain}")
            print(f"{'#'*64}")

            # Phase 3 -- crawl.
            crawl_results = await crawl_domain(domain, browser=bm)

            # Phase 4 -- preprocess each page.
            preprocessed: list[PreprocessedPage] = []
            for cr in crawl_results:
                if not cr.page_result.success:
                    print(f"\n  [SKIP] {cr.url} -- fetch failed: {cr.page_result.error}")
                    continue

                pp = preprocess_page(
                    url=cr.page_result.final_url or cr.url,
                    category=cr.category,
                    raw_html=cr.page_result.html,
                )
                preprocessed.append(pp)

                print(f"\n  [PREPROCESS]")
                print(f"  URL             : {pp.url}")
                print(f"  Category        : {pp.category}")
                print(f"  Original HTML   : {pp.original_html_chars:,} chars")
                print(f"  Clean text      : {pp.cleaned_text_chars:,} chars")
                print(f"  Reduction       : {pp.reduction_percentage}%")
                print(f"  Emails          : {len(pp.emails)}", end="")
                if pp.emails:
                    print(f"  {pp.emails}")
                else:
                    print()
                print(f"  LinkedIn URLs   : {len(pp.linkedin_urls)}", end="")
                if pp.linkedin_urls:
                    print(f"  {pp.linkedin_urls}")
                else:
                    print()

            # Summary.
            all_emails = sorted(set(
                e for pp in preprocessed for e in pp.emails
            ))
            all_linkedin = sorted(set(
                u for pp in preprocessed for u in pp.linkedin_urls
            ))
            total_clean = sum(pp.cleaned_text_chars for pp in preprocessed)

            print(f"\n  {'='*56}")
            print(f"  SUMMARY for {domain}")
            print(f"  Pages preprocessed : {len(preprocessed)}")
            print(f"  Total clean text   : {total_clean:,} chars")
            print(f"  Unique emails      : {len(all_emails)}  {all_emails}")
            print(f"  Unique LinkedIn    : {len(all_linkedin)}  {all_linkedin}")
            print(f"  {'='*56}")


async def main(domains: list[str]) -> None:
    """Run the enrichment pipeline for the given domains.

    Args:
        domains: List of company domains to enrich.
    """
    logger.info("Starting Lead Enrichment Agent")
    logger.info("Domains to process: %s", domains)

    # Phase 4 -- preprocessing smoke test.
    await preprocessing_smoke_test(domains)

    # TODO: Phase 5+ -- call extractor.enrich_domain() for each domain,
    #       collect results, and output as JSON.

    logger.info("Done.")


if __name__ == "__main__":
    # Accept domains from CLI args, or fall back to defaults.
    domains = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_DOMAINS
    asyncio.run(main(domains))
