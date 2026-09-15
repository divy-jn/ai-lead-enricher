"""
llm.py — LLM API interaction layer.

Handles sending cleaned text to the LLM and parsing the structured
response back into Pydantic models. Includes retry logic and error handling.
"""

from src.schemas import CompanyEnrichment
from src.utils import get_logger

logger = get_logger(__name__)


async def enrich_with_llm(
    domain: str,
    cleaned_texts: list[str],
) -> CompanyEnrichment:
    """Send preprocessed text to the LLM and get structured enrichment data.

    Args:
        domain: The company domain being enriched.
        cleaned_texts: List of cleaned text blocks from crawled pages.

    Returns:
        A validated CompanyEnrichment Pydantic model.

    Raises:
        RuntimeError: If the LLM call fails after retries.

    TODO: Implement in Phase 2.
    """
    raise NotImplementedError("LLM enrichment will be implemented in Phase 2")
