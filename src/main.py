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
from datetime import datetime, timezone
import os
from src.extractor import enrich_domains
from src.schemas import BatchResult

async def main(domains: list[str]) -> None:
    """Run the batch enrichment pipeline for the given domains."""
    logger.info("Starting Lead Enrichment Agent")
    
    results = await enrich_domains(domains)
    
    # Generate JSON output
    os.makedirs("output", exist_ok=True)
    batch_result = BatchResult(
        generated_at=datetime.now(timezone.utc).isoformat(),
        domains=results
    )
    
    output_path = "output/output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(batch_result.model_dump_json(indent=2))
        
    print("\n")
    # Print concise progress/results
    for i, res in enumerate(results, 1):
        print(f"[{i}/{len(results)}] {res.domain}")
        print(f"Crawl: {res.pages_successful}/{res.pages_crawled} pages successful")
        print(f"Preprocess: {res.pages_successful} pages")
        print(f"LLM: {res.total_tokens} tokens")
        print(f"Status: {res.status.upper()}")
        if res.error:
            print(f"Error: {res.error}")
        print()

    # Print final summary
    successful = sum(1 for r in results if r.status == "success")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "failed")
    total_tokens = sum(r.total_tokens for r in results)
    
    print("==================================================")
    print("BATCH SUMMARY")
    print("=============")
    print()
    print(f"Successful: {successful}/{len(results)}")
    print(f"Partial:    {partial}/{len(results)}")
    print(f"Failed:     {failed}/{len(results)}")
    print(f"Total tokens: {total_tokens}")
    print(f"Output: {output_path}")
    print("==========================")

    logger.info("Done.")


if __name__ == "__main__":
    domains = sys.argv[1:]
    if not domains:
        domains = ["postman.com", "supabase.com", "vapi.ai"]
        
    asyncio.run(main(domains))
