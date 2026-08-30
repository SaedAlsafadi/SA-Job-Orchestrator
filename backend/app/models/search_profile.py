"""Search profile database models."""

from sqlalchemy import Boolean, Float, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

class SearchProfile(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A profile defining an autonomous global job search strategy."""
    
    __tablename__ = "search_profiles"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    
    # Search parameters
    target_roles: Mapped[list[str]] = mapped_column(JSON, default=list)
    role_aliases: Mapped[list[str]] = mapped_column(JSON, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    excluded_keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    preferred_countries: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_cities: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    preferred_work_models: Mapped[list[str]] = mapped_column(JSON, default=list) # e.g., remote, hybrid, onsite
    employment_types: Mapped[list[str]] = mapped_column(JSON, default=list) # e.g., full-time, contract
    seniority: Mapped[list[str]] = mapped_column(JSON, default=list)
    
    excluded_companies: Mapped[list[str]] = mapped_column(JSON, default=list)
    preferred_companies: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Thresholds & Caps
    minimum_match_score: Mapped[float] = mapped_column(Float, default=80.0)
    max_preparations_per_cycle: Mapped[int] = mapped_column(Integer, default=3)
    max_preparations_per_day: Mapped[int] = mapped_column(Integer, default=10)
    
    # Scheduling
    frequency_minutes: Mapped[int] = mapped_column(Integer, default=60)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<SearchProfile(name='{self.name}', enabled={self.enabled})>"
