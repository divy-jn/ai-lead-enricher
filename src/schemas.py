"""
schemas.py — Pydantic models for structured enrichment output.

These schemas define the exact shape of data the agent produces.
"""

import re
from pydantic import BaseModel, Field, field_validator, model_validator

def _count_sentences(text: str) -> int:
    # Remove URLs so their periods aren't counted
    text_no_urls = re.sub(r'https?://[^\s]+', '', text)
    # Remove common abbreviations (case-insensitive)
    abbrevs = r'\b(?:Inc|Ltd|Co|Corp|LLC|Mr|Mrs|Ms|Dr|Prof|e\.g|i\.e)\.'
    text_no_abbrevs = re.sub(abbrevs, '', text_no_urls, flags=re.IGNORECASE)
    # Remove ellipses
    text_cleaned = re.sub(r'\.{2,}', '', text_no_abbrevs)
    # Find sentence-ending punctuation followed by space or end of string
    matches = re.findall(r'[.!?]+(?:\s+|$)', text_cleaned.strip())
    return len(matches)


class LeadershipEntry(BaseModel):
    """A single leadership team member."""

    name: str = Field(..., description="Full name of the person. Reject incomplete names (e.g. first name only) unless evidence clearly establishes it.")
    role: str = Field(..., description="Job title or role")
    linkedin_url: str | None = Field(
        None,
        description="LinkedIn profile URL, if explicitly found on the site and clearly associated with this person.",
    )


    @field_validator("name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        # A simple deterministic rule: reject names that are just a single short token
        # unless it's a known mononym (which we still reject for business reasons here).
        cleaned = v.strip()
        tokens = cleaned.split()
        if len(tokens) < 2:
            raise ValueError("Leadership name must be a sufficiently identifiable full name, not a single token.")
        return cleaned

class CompanyEnrichment(BaseModel):
    """Structured enrichment data for a single company domain."""

    domain: str = Field(..., description="The domain that was enriched")
    company_overview: str = Field(
        ...,
        description="Exactly 2 concise sentences describing the company based ONLY on supplied evidence.",
    )
    target_audience: str = Field(
        ...,
        description="Who the company primarily serves (ICP), based ONLY on supplied evidence.",
    )
    primary_generic_contacts: list[str] = Field(
        default_factory=list,
        description="Primary generic contact emails (e.g., sales@, contact@, info@, support@).",
    )
    other_public_contacts: list[str] = Field(
        default_factory=list,
        description="Other compliance/administrative emails (e.g., legal@, privacy@, security@, abuse@).",
    )
    contact_points: list[str] = Field(
        default_factory=list,
        description="Union of primary and other contacts. Will be computed automatically.",
    )
    leadership: list[LeadershipEntry] = Field(
        default_factory=list,
        description="Key leadership team members discovered on the site. DO NOT invent people. LinkedIn URLs must only come from explicit evidence.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the enrichment data (0.0-1.0).",
    )
    source_urls: list[str] = Field(
        default_factory=list,
        description="List of URLs actually fetched and used as evidence.",
    )

    @field_validator("company_overview")
    @classmethod
    def validate_two_sentences(cls, v: str) -> str:
        count = _count_sentences(v)
        if count != 2:
            raise ValueError(f"company_overview must be exactly 2 sentences. Found {count}.")
        return v
        
    @model_validator(mode="after")
    def compute_contact_points(self):
        combined = set(self.primary_generic_contacts + self.other_public_contacts)
        # Only overwrite if contact_points is empty, or union them
        self.contact_points = list(set(self.contact_points) | combined)
        return self


class LLMResult(BaseModel):
    """Result object capturing the parsed data and token usage from the LLM."""
    
    data: CompanyEnrichment
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


from typing import Literal

class DomainResult(BaseModel):
    """The complete processing result for a single domain in the batch pipeline."""
    
    domain: str = Field(..., description="The domain processed")
    status: Literal["success", "partial", "failed"] = Field(
        ..., description="Overall status of the enrichment process for this domain"
    )
    data: CompanyEnrichment | None = Field(
        None, description="The enriched company data, if successful or partially successful"
    )
    error: str | None = Field(None, description="Error message if the domain failed to process")
    
    # Operational metadata
    discovery_method: str = Field("homepage_links", description="Method used to discover pages (e.g., homepage_links, sitemap, robots_sitemap, none)")
    pages_discovered: int = Field(0, description="Total number of pages discovered")
    pages_crawled: int = Field(0, description="Total number of pages attempted to fetch")
    pages_successful: int = Field(0, description="Total number of pages successfully fetched and parsed")
    pages_failed: int = Field(0, description="Total number of pages that failed to fetch")
    
    # Token usage
    prompt_tokens: int = Field(0, description="Tokens used for the prompt")
    completion_tokens: int = Field(0, description="Tokens used for the completion")
    total_tokens: int = Field(0, description="Total tokens used for this domain")


class BatchResult(BaseModel):
    """The top-level JSON structure for the batch processing output."""
    
    generated_at: str = Field(..., description="ISO 8601 timestamp of when the batch completed")
    domains: list[DomainResult] = Field(
        default_factory=list, description="List of results for each processed domain"
    )
