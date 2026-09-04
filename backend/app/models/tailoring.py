"""Tailoring session database models."""

from sqlalchemy import ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.models.enums import TailoringStatus, ChangeType, ReviewerStatus, ReviewSeverity

class CVTailoringSession(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A tailoring session containing changes applied to a base resume for a specific job."""
    
    __tablename__ = "cv_tailoring_sessions"
    __table_args__ = (Index("ix_tailoring_status", "status"),)
    
    job_id: Mapped[str] = mapped_column(String(32), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    base_resume_id: Mapped[str] = mapped_column(String(32), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    
    # Snapshot metadata
    base_resume_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    candidate_profile_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # State
    status: Mapped[TailoringStatus] = mapped_column(pg_enum(TailoringStatus, "tailoring_status"), nullable=False, default=TailoringStatus.DRAFT)
    
    # Model tracking
    tailor_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Related final resume if completed
    final_resume_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    
    changes: Mapped[list["CVTailoringChange"]] = relationship("CVTailoringChange", back_populates="session", cascade="all, delete-orphan")


class CVTailoringChange(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A single proposed change inside a tailoring session."""
    
    __tablename__ = "cv_tailoring_changes"
    
    session_id: Mapped[str] = mapped_column(String(32), ForeignKey("cv_tailoring_sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Stable identifier used for UI matching or regeneration tracking
    change_id: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Target location in canonical ResumeDocument
    target_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. INLINE_TEXT, BULLET, SECTION, SUMMARY
    target_reference: Mapped[str] = mapped_column(String(200), nullable=False) # e.g. 'experience[0].description'
    section: Mapped[str] = mapped_column(String(100), nullable=False)
    
    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    change_type: Mapped[ChangeType] = mapped_column(pg_enum(ChangeType, "change_type"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Arrays stored as JSON
    linked_requirement_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    linked_evidence_ids: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    
    # Review pass
    review_severity: Mapped[ReviewSeverity] = mapped_column(pg_enum(ReviewSeverity, "review_severity"), nullable=False, default=ReviewSeverity.SAFE)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # User decision
    user_decision: Mapped[ReviewerStatus] = mapped_column(pg_enum(ReviewerStatus, "reviewer_status"), nullable=False, default=ReviewerStatus.PENDING)
    
    session: Mapped["CVTailoringSession"] = relationship("CVTailoringSession", back_populates="changes")
