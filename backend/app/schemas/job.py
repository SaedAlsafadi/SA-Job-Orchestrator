"""Pydantic schemas for job-related API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpportunityOperationalState(BaseModel):
    """Related-record summary used to resolve one safe next action."""

    match_exists: bool = False
    tailoring_session_id: str | None = None
    tailoring_status: str | None = None
    tailored_resume_id: str | None = None
    tailored_resume_verified: bool = False
    application_id: str | None = None
    application_status: str | None = None
    package_id: str | None = None
    package_version: int | None = None
    package_ready: bool = False
    package_approved: bool = False
    route_type: str | None = None
    route_url: str | None = None


class JobSearchRequest(BaseModel):
    """Request body for multi-platform job search."""

    query: str = Field(..., min_length=1, max_length=500)
    location: str = ""
    platforms: list[str] = Field(
        default_factory=lambda: ["linkedin", "indeed", "glassdoor"]
    )
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=20, ge=1, le=100)


class JobListingResponse(BaseModel):
    """Single job listing in API responses."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    platform: str
    platform_job_id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    salary_range: str | None = None
    job_type: str | None = None
    remote: bool = False
    posted_date: datetime | None = None
    experience_level: str | None = None
    match_score: float | None = None
    operational_state: OpportunityOperationalState = Field(
        default_factory=OpportunityOperationalState
    )
    skills_required: dict | None = None
    status: str

    # Phase 18 fields
    source_type: str | None = None
    raw_data: dict | None = None
    data_quality_flags: dict | None = None
    detected_language: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("match_score", mode="before")
    @classmethod
    def normalize_match_score(cls, value: float | None) -> float | None:
        """Canonical API shape is 0..1; legacy rows stored 0..100."""
        if value is None:
            return None
        score = float(value)
        return score / 100 if abs(score) > 1 else score


class JobDetailResponse(JobListingResponse):
    """Single job detail response — includes eagerly-loaded routes."""

    routes: list["ApplicationRouteResponse"] | None = None


class ApplicationRouteResponse(BaseModel):
    """JSON-safe application route projection for job details."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    route_type: str
    url: str | None = None
    email: str | None = None
    instructions: str | None = None
    confidence: float
    resolution_reason: str | None = None
    requires_human: bool
    is_preferred: bool
    resolved_at: datetime


class JobListResponse(BaseModel):
    """Paginated list of job listings."""

    items: list[JobListingResponse]
    total: int
    page: int
    page_size: int
    has_next: bool


class JobAnalysisResponse(BaseModel):
    """Response for job analysis endpoint."""

    job_id: str
    match_score: float
    skill_match: float
    keyword_match: float
    missing_skills: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
