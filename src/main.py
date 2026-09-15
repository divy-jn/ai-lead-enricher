"""
main.py -- CLI entry point for the Lead Enrichment Agent.

Accepts company domains as arguments and runs the enrichment pipeline.

Usage:
    python -m src.main postman.com supabase.com vapi.ai
"""

import asyncio
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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


import json
from src.extractor import enrich_domain

async def enrichment_smoke_test(domain: str) -> None:
    """Run the full enrichment pipeline for a single domain and print the results."""
    print(f"\n{'#'*64}")
    print(f"#  DOMAIN: {domain}")
    print(f"{'#'*64}\n")

    # The BrowserManager will be instantiated and closed automatically by enrich_domain
    # but we could also pass it in. For the smoke test, we'll let enrich_domain handle it.
    
    result = await enrich_domain(domain)
    
    if not result:
        print(f"\n[ERROR] Enrichment failed for {domain}. Check logs for details.")
        return

    print(f"\n{'='*56}")
    print(f"ENRICHMENT RESULTS FOR: {domain}")
    print(f"{'='*56}\n")
    
    # Print the Pydantic model as formatted JSON
    print(result.data.model_dump_json(indent=2))
    
    print(f"\n{'='*56}")
    print(f"TOKEN USAGE")
    print(f"{'='*56}")
    print(f"Prompt tokens     : {result.prompt_tokens}")
    print(f"Completion tokens : {result.completion_tokens}")
    print(f"Total tokens      : {result.total_tokens}")
    print(f"{'='*56}\n")


async def main(domains: list[str]) -> None:
    """Run the enrichment pipeline for the given domains.

    Args:
        domains: List of company domains to enrich.
    """
    logger.info("Starting Lead Enrichment Agent")
    
    # User requested to run ONLY postman.com for this smoke test
    test_domain = "postman.com"
    logger.info(f"Running Phase 5 smoke test on {test_domain}")

    await enrichment_smoke_test(test_domain)

    logger.info("Done.")


if __name__ == "__main__":
    # For Phase 5 we ignore sys.argv and just run postman.com as requested
    asyncio.run(main(DEFAULT_DOMAINS))
