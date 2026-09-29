"""Application package model (Phase 19 — Application Intelligence).

An :class:`ApplicationPackage` is an **immutable, version-locked snapshot** of everything
that would be submitted for one application: the resume version, cover letter, application
email, answers, and the selected route. Regenerating or editing any component creates a NEW
package row (``version + 1``); existing rows are never mutated, so an approved package is
always exactly reproducible.

Version locking: ``content_hash`` is a SHA-256 over every component reference. Approval
(:class:`~app.models.application.ApplicationApproval`) binds to ``(package_id,
package_hash)`` — if any component changes, the new package has a different hash and the
old approval can never authorize it.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    pg_enum,
)
from app.models.enums import EmailSendState, QAVerdict


class ApplicationPackage(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """An immutable, versioned submission package for an application."""

    __tablename__ = "application_packages"
    __table_args__ = (
        Index("ix_package_application", "application_id"),
        Index("ix_package_current", "application_id", "is_current"),
    )

    # Ownership chain
    application_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    # Selected route (EMAIL / WORKABLE / ...) — SET NULL: a deleted route must not
    # destroy the historical package record.
    route_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("application_routes.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- Immutable component references (version locking) ---
    # Resume: an immutable Resume row (tailored/verified via the tailoring workbench).
    resume_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    # Cover letter: storage key + plain text snapshot (the text is what the user reviewed).
    cover_letter_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_letter_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Application email: the EXACT content the user approved.
    email_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Attachment storage keys (resume/cover letter) that will actually be attached.
    attachment_keys: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # Answers snapshot: [{question, answer, status, confidence}]
    answers: Mapped[list | None] = mapped_column(JSON, nullable=True)

    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    # --- Versioning ---
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # SHA-256 over all component references — the package fingerprint approvals bind to.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=True, nullable=False)

    # --- QA result (annotation, not a component — does not change the hash) ---
    qa_verdict: Mapped[QAVerdict | None] = mapped_column(
        pg_enum(QAVerdict, "qa_verdict"), nullable=True
    )
    qa_issues: Mapped[list | None] = mapped_column(JSON, nullable=True)
    qa_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # --- Approval binding (set when the user approves THIS exact version) ---
    approval_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Send record (email route) ---
    send_state: Mapped[EmailSendState | None] = mapped_column(
        pg_enum(EmailSendState, "email_send_state"), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    provider_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    sender_address: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # Relationships
    application: Mapped["Application"] = relationship()
    resume: Mapped["Resume | None"] = relationship()
    route: Mapped["ApplicationRoute | None"] = relationship()

    def __repr__(self) -> str:
        return (
            f"<ApplicationPackage(id={self.id}, application_id={self.application_id}, "
            f"version={self.version}, hash={self.content_hash[:8]})>"
        )
