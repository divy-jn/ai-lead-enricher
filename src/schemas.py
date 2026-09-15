"""
schemas.py — Pydantic models for structured enrichment output.

These schemas define the exact shape of data the agent produces.
"""

from pydantic import BaseModel, Field


class LeadershipEntry(BaseModel):
    """A single leadership team member."""

    name: str = Field(..., description="Full name of the person")
    role: str = Field(..., description="Job title or role")
    linkedin_url: str | None = Field(
        None,
        description="LinkedIn profile URL, if explicitly found on the site",
    )


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
    contact_points: list[str] = Field(
        default_factory=list,
        description="Generic/public email addresses found on the site. Empty list if none found. DO NOT invent emails.",
    )
    leadership: list[LeadershipEntry] = Field(
        default_factory=list,
        description="Key leadership team members discovered on the site. DO NOT invent people. LinkedIn URLs must only come from explicit evidence.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the enrichment data (0.0-1.0). Must reflect evidence completeness.",
    )


class LLMResult(BaseModel):
    """Result object capturing the parsed data and token usage from the LLM."""
    
    data: CompanyEnrichment
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
