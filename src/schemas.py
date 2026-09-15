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
        description="Exactly 2 concise sentences describing the company",
    )
    target_audience: str = Field(
        ...,
        description="Who the company primarily serves",
    )
    contact_points: list[str] = Field(
        default_factory=list,
        description="Generic/public email addresses found on the site",
    )
    leadership: list[LeadershipEntry] = Field(
        default_factory=list,
        description="Key leadership team members discovered on the site",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in the enrichment data (0.0–1.0)",
    )
