"""Company Watch database models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

class CompanyWatch(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A schedule to continuously monitor jobs from a specific employer/ATS."""

    __tablename__ = "company_watches"

    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. WORKABLE
    source_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    
    interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Thresholds
    match_threshold: Mapped[float] = mapped_column(Float, default=80.0)
    max_preparations_per_cycle: Mapped[int] = mapped_column(Integer, default=3)

    def __repr__(self) -> str:
        return f"<CompanyWatch(company='{self.company_name}', platform='{self.platform}')>"
