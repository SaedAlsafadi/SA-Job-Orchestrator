"""Pydantic schemas for CV tailoring."""

from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.enums import TailoringStatus, ChangeType, ReviewerStatus, ReviewSeverity

class CVTailoringChangeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str
    target_type: str
    target_reference: str
    section: str
    
    original_text: str | None = None
    proposed_text: str | None = None
    
    change_type: ChangeType
    reason: str
    
    linked_requirement_ids: list[str] = Field(default_factory=list)
    linked_evidence_ids: list[str] = Field(default_factory=list)
    
    review_severity: ReviewSeverity
    review_reason: str | None = None
    
    user_decision: ReviewerStatus

class CVTailoringSessionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    base_resume_id: str
    base_resume_version: str | None = None
    candidate_profile_version: str | None = None
    status: TailoringStatus
    tailor_model: str | None = None
    review_model: str | None = None
    final_resume_id: str | None = None
    created_at: datetime
    updated_at: datetime
    
    changes: list[CVTailoringChangeSchema] = Field(default_factory=list)

class CVTailoringStartRequest(BaseModel):
    job_id: str
    base_resume_id: str

class CVTailoringDecisionsRequest(BaseModel):
    decisions: dict[str, ReviewerStatus] # change_id -> decision

class CVTailoringReviseRequest(BaseModel):
    change_id: str
    instructions: str | None = None

class ProposedChangeOutput(BaseModel):
    section: str
    target_type: str = Field(description="INLINE_TEXT, BULLET, SECTION, SUMMARY")
    target_reference: str = Field(description="Stable reference e.g., 'experience[0].description'")
    change_type: ChangeType
    original_text: str | None = Field(description="The exact original text being replaced or removed, if applicable.")
    proposed_text: str | None = Field(description="The exact new text being proposed, if applicable.")
    reason: str = Field(description="Why this change improves the match.")
    linked_requirement_ids: list[str] = Field(default_factory=list, description="Job requirements that motivated this change.")
    linked_evidence_ids: list[str] = Field(default_factory=list, description="Candidate evidence IDs that support this claim. MUST BE REAL.")

class CVTailorOutput(BaseModel):
    changes: list[ProposedChangeOutput]

class ReviewDecisionOutput(BaseModel):
    change_id: str
    severity: ReviewSeverity
    reason: str = Field(description="Concise explanation if warning or blocked.")

class CVReviewOutput(BaseModel):
    reviews: list[ReviewDecisionOutput]
