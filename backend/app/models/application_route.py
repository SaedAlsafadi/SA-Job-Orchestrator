"""Application Route database model."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class ApplicationRoute(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """A route indicating how to apply for a discovered job."""

    __tablename__ = "application_routes"

    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    
    route_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., WORKABLE, EMAIL, COMPANY_WEBSITE, LINKEDIN, MANUAL
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    resolution_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requires_human: Mapped[bool] = mapped_column(Boolean, default=False)
    is_preferred: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    job: Mapped["Job"] = relationship(back_populates="routes") # noqa: F821

    def __repr__(self) -> str:
        return f"<ApplicationRoute(route_type='{self.route_type}', confidence={self.confidence}, preferred={self.is_preferred})>"
