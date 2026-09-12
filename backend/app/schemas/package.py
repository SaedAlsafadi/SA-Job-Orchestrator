"""Application package schemas (Phase 19)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmailSendState, QAVerdict


class PackageCreate(BaseModel):
    """Create/update an application package. Omitted components carry over."""

    model_config = ConfigDict(extra="forbid")

    route_id: str | None = None
    resume_id: str | None = None
    cover_letter_text: str | None = None
    email_to: str | None = Field(default=None, description="User-verified recipient")
    email_subject: str | None = None
    email_body: str | None = None
    answers: list[dict] | None = None
    language: str = "en"


class PackageResponse(BaseModel):
    """An immutable application package version."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    application_id: str
    job_id: str
    route_id: str | None = None
    resume_id: str | None = None
    cover_letter_key: str | None = None
    cover_letter_text: str | None = None
    email_to: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    attachment_keys: list[str] | None = None
    answers: list[dict] | None = None
    language: str
    version: int
    content_hash: str
    is_current: bool
    qa_verdict: QAVerdict | None = None
    qa_issues: list[dict] | None = None
    approval_id: str | None = None
    approved_at: datetime | None = None
    send_state: EmailSendState | None = None
    sent_at: datetime | None = None
    message_id: str | None = None
    created_at: datetime


class ReadinessResponse(BaseModel):
    """Concise readiness summary: "What remains before I can apply?"."""

    ready: bool
    missing: list[str]
    warnings: list[str]
    documents: list[dict]
    route: str | None = None
    route_url: str | None = None
    route_instructions: str | None = None
    posting_quality: dict
    work_authorization: dict
    package_version: int
    content_hash: str
    approved: bool
    send_state: str | None = None


class CoverLetterGenRequest(BaseModel):
    match_summary: dict | None = None
    language: str = "en"


class EmailGenRequest(BaseModel):
    language: str = "en"


class AnswersGenRequest(BaseModel):
    questions: list[str]
    language: str = "en"


class SendResultResponse(BaseModel):
    state: str
    message_id: str | None = None
    provider_response: str | None = None
    error: str | None = None
