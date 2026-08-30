"""Discovery Run models."""

from sqlalchemy import Float, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin

class DiscoveryRun(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    """An execution instance of a SearchProfile or CompanyWatch."""

    __tablename__ = "discovery_runs"

    # Polymorphic associations
    search_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE"), nullable=True
    )
    company_watch_id: Mapped[str | None] = mapped_column(
        ForeignKey("company_watches.id", ondelete="CASCADE"), nullable=True
    )

    status: Mapped[str] = mapped_column(String(50), nullable=False)  # running, success, failed, partial_success
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_errors: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Metrics
    queries_generated: Mapped[int] = mapped_column(Integer, default=0)
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, default=0)
    jobs_eligible: Mapped[int] = mapped_column(Integer, default=0)
    jobs_matched: Mapped[int] = mapped_column(Integer, default=0)
    jobs_selected: Mapped[int] = mapped_column(Integer, default=0)

    # Detailed statistics
    skipped_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<DiscoveryRun(status='{self.status}', jobs_found={self.jobs_found})>"
