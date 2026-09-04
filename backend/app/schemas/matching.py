from enum import StrEnum
from pydantic import BaseModel, Field
from datetime import datetime
from app.services.eligibility import EligibilityResult

class MatchEvidence(BaseModel):
    evidence_id: str = Field(description="The exact evidence_id from the CandidateProfile")
    description: str = Field(description="Why this evidence is relevant to the job")

class RequirementStatus(StrEnum):
    MATCH = "MATCH"
    PARTIAL = "PARTIAL"
    GAP = "GAP"
    UNKNOWN = "UNKNOWN"

class RequirementImportance(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class RequirementAnalysis(BaseModel):
    requirement_id: str = Field(description="A unique short identifier like 'req-1'")
    original_text: str = Field(description="The raw requirement text from the job description")
    normalized_requirement: str = Field(description="A clean, concise statement of the requirement")
    category: str = Field(description="e.g., 'Skills', 'Experience', 'Education', 'Other'")
    importance: RequirementImportance
    status: RequirementStatus
    evidence_ids: list[str] = Field(description="Exact evidence_ids from CandidateProfile supporting the status", default_factory=list)
    explanation: str = Field(description="Short explanation of the candidate's status against this requirement")

class DimensionStatus(StrEnum):
    VALID_SCORE = "VALID_SCORE"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_APPLICABLE = "NOT_APPLICABLE"

class DimensionScore(BaseModel):
    status: DimensionStatus
    score: int | None = Field(default=None, description="Score 0-100 if valid")
    explanation: str | None = None

class MatchVerdict(StrEnum):
    STRONG_MATCH = "STRONG_MATCH"
    GOOD_MATCH = "GOOD_MATCH"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    WEAK_MATCH = "WEAK_MATCH"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

class MatchDimensions(BaseModel):
    skills: DimensionScore
    experience: DimensionScore
    role_alignment: DimensionScore
    # We can keep some legacy fields just in case they are used elsewhere, but ideally they migrate
    # For now, just these 3 as requested.
    ats_keywords: DimensionScore | None = None

class LLMMatchResult(BaseModel):
    verdict: MatchVerdict
    confidence: float = Field(description="Confidence in this match result from 0.0 to 1.0")
    data_quality: str = Field(description="'HIGH', 'LIMITED', or 'POOR'")
    data_quality_explanation: str | None = Field(default=None)
    explanation: str = Field(description="2-4 sentences explaining why this candidate is a good/bad/uncertain match")
    recommendation: str = Field(description="'apply', 'review', or 'skip'")
    strong_matches: list[str] = Field(description="Concise points of strong alignment")
    gaps: list[str] = Field(description="Concise missing skills or experience")
    critical_gaps: list[str] = Field(description="Dealbreaker gaps or missing requirements")
    blockers: list[str] = Field(description="Genuine blockers like hard eligibility fails or missing work auth")
    dimensions: MatchDimensions
    requirement_analysis: list[RequirementAnalysis]

class MatchProvenance(BaseModel):
    candidate_profile_version: int
    matching_algorithm_version: str
    model_provider: str
    model_name: str
    generated_at: datetime
    ats_method: str = "deterministic_fallback"

class CandidateMatchResult(BaseModel):
    eligibility: EligibilityResult
    total_score: int | None = None
    verdict: MatchVerdict
    confidence: float
    data_quality: str
    data_quality_explanation: str | None = None
    explanation: str
    recommendation: str
    dimensions: MatchDimensions
    strong_matches: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    critical_gaps: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    requirement_analysis: list[RequirementAnalysis] = Field(default_factory=list)
    provenance: MatchProvenance

