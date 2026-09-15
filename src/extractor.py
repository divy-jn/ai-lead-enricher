"""
extractor.py — Enrichment pipeline orchestrator.

Ties together the crawler, preprocessor, and LLM modules into a
single pipeline: crawl → preprocess → enrich → validate.
"""

from src.schemas import CompanyEnrichment
from src.utils import get_logger

logger = get_logger(__name__)


async def enrich_domain(domain: str) -> CompanyEnrichment | None:
    """Run the full enrichment pipeline for a single domain.

    Steps:
        1. Crawl relevant pages for the domain.
        2. Clean and preprocess the raw HTML.
        3. Send cleaned text to the LLM for structured extraction.
        4. Return the validated CompanyEnrichment model.

    Args:
        domain: The company domain to enrich (e.g., "postman.com").

    Returns:
        A CompanyEnrichment model on success, or None if the pipeline fails.

    TODO: Implement in Phase 2.
    """
    raise NotImplementedError("Enrichment pipeline will be implemented in Phase 2")
