"""Candidate Profile database model."""

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CandidateProfile(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """The authoritative domain model for a user's professional profile.
    
    Nested complex data (skills, experience, etc.) is stored as JSON and validated
    by the Pydantic schemas in the application layer before persistence.
    """

    __tablename__ = "candidate_profiles"

    user_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    
    # Audit versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # JSON Document columns (Validated by Pydantic)
    identity: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    location: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    employment: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    work_authorization: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    education: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    experience: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    projects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    certifications: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    languages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Note: `user` relationship requires `CandidateProfile` back_populates on `User`
    user: Mapped["User"] = relationship(back_populates="profile")  # type: ignore

    def __repr__(self) -> str:
        return f"<CandidateProfile(id={self.id}, user_id={self.user_id}, version={self.version})>"


class CandidateProfileVersion(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Historical versions of a candidate profile."""

    __tablename__ = "candidate_profile_versions"

    profile_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("candidate_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    
    # Store the entire snapshot as JSON
    profile_data: Mapped[dict] = mapped_column(JSON, nullable=False)

    def __repr__(self) -> str:
        return f"<CandidateProfileVersion(profile_id={self.profile_id}, version={self.version})>"

