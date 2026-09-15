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
from src.utils import get_logger

logger = get_logger(__name__)

DEFAULT_DOMAINS = [
    "postman.com",
    "supabase.com",
    "vapi.ai",
]


async def crawler_smoke_test(domains: list[str]) -> None:
    """Discover and fetch relevant pages for each domain.

    This is a temporary smoke test for the crawler layer (Phase 3).
    It will be replaced by the full enrichment pipeline in later phases.
    """
    async with BrowserManager() as bm:
        for domain in domains:
            print(f"\n{'#'*64}")
            print(f"#  CRAWLING: {domain}")
            print(f"{'#'*64}")

            results = await crawl_domain(domain, browser=bm)

            for cr in results:
                status = "OK" if cr.page_result.success else "FAIL"
                html_len = len(cr.page_result.html)
                print(
                    f"  [{status}] [{cr.category:<12}] "
                    f"{cr.url}  "
                    f"(HTTP {cr.page_result.status_code}, "
                    f"{html_len:,} chars)"
                )
                if cr.page_result.error:
                    print(f"       Error: {cr.page_result.error}")

            ok = sum(1 for r in results if r.page_result.success)
            print(f"\n  Total: {len(results)} pages, {ok} succeeded")


async def main(domains: list[str]) -> None:
    """Run the enrichment pipeline for the given domains.

    Args:
        domains: List of company domains to enrich.
    """
    logger.info("Starting Lead Enrichment Agent")
    logger.info("Domains to process: %s", domains)

    # Phase 3 -- crawler smoke test.
    await crawler_smoke_test(domains)

    # TODO: Phase 4+ -- call extractor.enrich_domain() for each domain,
    #       collect results, and output as JSON.

    logger.info("Done.")


if __name__ == "__main__":
    # Accept domains from CLI args, or fall back to defaults.
    domains = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_DOMAINS
    asyncio.run(main(domains))
