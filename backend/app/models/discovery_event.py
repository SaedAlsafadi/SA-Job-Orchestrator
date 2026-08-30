"""Discovery Event model for multiple discovery occurrences of the same Job."""

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

class DiscoveryEvent(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """Records a specific occurrence of finding a job opportunity."""

    __tablename__ = "discovery_events"

    job_id: Mapped[str] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    
    discovery_provider: Mapped[str] = mapped_column(String(50), nullable=False) # e.g. EXA, WORKABLE
    discovery_query: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    job: Mapped["Job"] = relationship(back_populates="discovery_events") # noqa: F821

    def __repr__(self) -> str:
        return f"<DiscoveryEvent(provider='{self.discovery_provider}', job_id='{self.job_id}')>"
