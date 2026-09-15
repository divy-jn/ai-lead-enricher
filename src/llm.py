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
1. USE ONLY SUPPLIED EVIDENCE: Do not use prior knowledge. Do not fill missing information from memory.
2. NEVER INVENT FACTS: Do not hallucinate. Do not invent names, roles, or emails.
3. CONTACTS: Only use emails explicitly present in the supplied evidence. Never synthesize or infer email addresses.
4. CONTACT CLASSIFICATION: Place sales/support/general emails (e.g., sales@, info@) in `primary_generic_contacts`. Place compliance/admin emails (e.g., legal@, privacy@, security@, abuse@) in `other_public_contacts`.
5. LEADERSHIP RULES: You must only create a leadership entry when the evidence contains BOTH a sufficiently identifiable full name and an explicit company-associated role/title. Omit ambiguous candidates. DO NOT complete partial names from memory. DO NOT infer titles. DO NOT invent people. DO NOT guess LinkedIn URLs.
6. LINKEDIN URLS: Only return a LinkedIn URL when explicitly supported by evidence connecting the person to the URL. Do not guess or infer LinkedIn URLs.
7. MISSING EVIDENCE: Use empty strings, empty lists, or null where allowed if evidence is lacking.
8. COMPANY OVERVIEW: Must contain EXACTLY 2 sentences based ONLY on supplied evidence.
9. CONFIDENCE SCORE: Provide an internal estimate (0.0 to 1.0) of your confidence based on the quality of the evidence.

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
        
    # Group pages by evidence category
    grouped_pages: dict[str, list[PreprocessedPage]] = {
        "COMPANY": [],
        "LEADERSHIP": [],
        "CONTACT": [],
        "ICP / PRODUCT": [],
        "OTHER": []
    }
    
    for page in pages:
        cat = (page.category or "uncategorised").lower()
        if cat in ("about", "company", "homepage", "press", "news", "media"):
            grouped_pages["COMPANY"].append(page)
        elif cat in ("leadership", "team", "founders", "management", "careers"):
            grouped_pages["LEADERSHIP"].append(page)
        elif cat in ("contact", "support"):
            grouped_pages["CONTACT"].append(page)
        elif cat in ("product", "pricing", "customers"):
            grouped_pages["ICP / PRODUCT"].append(page)
        else:
            grouped_pages["OTHER"].append(page)
            
    for section_name, section_pages in grouped_pages.items():
        if not section_pages:
            continue
            
        prompt += f"=== {section_name} EVIDENCE ===\n"
        for page in section_pages:
            prompt += f"[Source URL: {page.url}]\n{page.text}\n"
            prompt += "-" * 40 + "\n"
        prompt += "\n"
        
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
