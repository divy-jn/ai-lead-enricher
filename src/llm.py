"""
llm.py — LLM API interaction layer.

Handles sending cleaned text to the LLM and parsing the structured
response back into Pydantic models. Includes retry logic and error handling.
"""
import json
import asyncio
from typing import Any
from pydantic import ValidationError
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError

from src.schemas import CompanyEnrichment, LLMResult
from src.utils import get_logger
from src.config import settings
from src.preprocessing import PreprocessedPage

logger = get_logger(__name__)


def _build_system_prompt() -> str:
    """Construct the system prompt containing the JSON schema and instructions."""
    schema = CompanyEnrichment.model_json_schema()
    
    return f"""You are an expert data extraction AI. Your task is to extract structured information about a company based ONLY on the supplied website evidence.

STRICT RULES:
1. USE ONLY SUPPLIED EVIDENCE: Do not use prior knowledge. If the website evidence does not contain the answer, leave the field empty (or null).
2. NEVER INVENT FACTS: Do not hallucinate.
3. NEVER INVENT EMAILS: Only extract emails explicitly found in the evidence.
4. CONTACT CLASSIFICATION: Place sales/support/general emails (e.g., sales@, info@) in `primary_generic_contacts`. Place compliance/admin emails (e.g., legal@, privacy@, security@, abuse@) in `other_public_contacts`.
5. LEADERSHIP RULES: You must only create a leadership entry when the evidence contains BOTH the person's name and role/title. Do NOT accept incomplete names (e.g., "Seth") unless explicitly established by evidence.
6. LINKEDIN URLS: Leadership LinkedIn URLs may only be populated when the supplied evidence explicitly supports the mapping between the person and the URL. Do NOT assign generic company URLs to an individual.
7. MISSING EVIDENCE: Use empty strings, empty lists, or null where allowed if evidence is lacking.
8. COMPANY OVERVIEW: Must contain EXACTLY 2 sentences.
9. CONFIDENCE SCORE: Provide an internal estimate (0.0 to 1.0) of your confidence.

You must output a single valid JSON object that strictly conforms to the following JSON Schema:

{json.dumps(schema, indent=2)}
"""

def _build_user_prompt(domain: str, pages: list[PreprocessedPage]) -> str:
    """Format the preprocessed pages and extracted hints into the user prompt."""
    prompt = f"Extract company enrichment data for the domain: {domain}\n\n"
    
    # Collect deterministic hints
    all_emails = set()
    all_linkedin = set()
    for page in pages:
        all_emails.update(page.emails)
        all_linkedin.update(page.linkedin_urls)
        
    if all_emails:
        prompt += f"DETERMINISTIC EMAILS FOUND (Use as evidence if appropriate):\n"
        prompt += ", ".join(all_emails) + "\n\n"
        
    if all_linkedin:
        prompt += f"DETERMINISTIC LINKEDIN URLS FOUND (Use as evidence if appropriate):\n"
        prompt += ", ".join(all_linkedin) + "\n\n"
        
    prompt += "WEBSITE EVIDENCE:\n"
    prompt += "=" * 40 + "\n"
    
    for page in pages:
        category = page.category.upper() if page.category else "PAGE"
        prompt += f"[{category}]\nURL: {page.url}\n\n{page.text}\n"
        prompt += "-" * 40 + "\n"
        
    return prompt


async def enrich_with_llm(
    domain: str,
    pages: list[PreprocessedPage],
) -> LLMResult:
    """Send preprocessed text to the LLM and get structured enrichment data.

    Args:
        domain: The company domain being enriched.
        pages: List of preprocessed pages.

    Returns:
        A validated LLMResult containing the CompanyEnrichment data and token usage.

    Raises:
        RuntimeError: If the LLM call fails after retries.
    """
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is missing. Please configure it in .env.")

    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout_s,
    )
    
    system_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(domain, pages)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error = None
    for attempt in range(1, settings.llm_max_retries + 1):
        content = None
        try:
            logger.info(f"LLM extraction for {domain} (attempt {attempt}/{settings.llm_max_retries})")
            
            response = await client.chat.completions.create(
                model=settings.llm_model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("LLM returned empty content")
                
            # Strictly validate with Pydantic
            enrichment_data = CompanyEnrichment.model_validate_json(content)
            
            # Extract token usage
            prompt_tokens = response.usage.prompt_tokens if response.usage else None
            completion_tokens = response.usage.completion_tokens if response.usage else None
            total_tokens = response.usage.total_tokens if response.usage else None
            
            logger.info(f"Successfully extracted data for {domain} (Tokens: {total_tokens})")
            
            return LLMResult(
                data=enrichment_data,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )

        except (APIError, APITimeoutError, RateLimitError) as e:
            last_error = e
            logger.warning(f"LLM API error on attempt {attempt}: {e}")
            if attempt < settings.llm_max_retries:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
        except (ValueError, ValidationError) as e:
            last_error = e
            logger.warning(f"LLM validation error on attempt {attempt}: {e}")
            if attempt < settings.llm_max_retries:
                if content is not None:
                    messages.append({"role": "assistant", "content": content})
                
                # concise error msg to avoid huge prompts
                err_msg = str(e)
                if isinstance(e, ValidationError):
                    # extract just the error messages for brevity
                    err_msg = "; ".join([f"{err['loc'][0] if err.get('loc') else 'root'}: {err['msg']}" for err in e.errors()])
                
                messages.append({
                    "role": "user", 
                    "content": f"Your previous output failed validation: {err_msg}. Please return a valid JSON object matching the schema exactly."
                })
                
    logger.error(f"Failed to enrich {domain} after {settings.llm_max_retries} attempts.")
    raise RuntimeError(f"LLM extraction failed for {domain}: {last_error}")
