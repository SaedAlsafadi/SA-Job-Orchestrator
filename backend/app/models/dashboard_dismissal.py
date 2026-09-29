"""User-scoped dashboard feed dismissals."""

from datetime import datetime

from sqlalchemy import DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, UUIDPrimaryKeyMixin


class DashboardDismissal(UUIDPrimaryKeyMixin, TenantMixin, Base):
    """Hide one material version of an entity from the dashboard only."""

    __tablename__ = "dashboard_dismissals"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "entity_type",
            "entity_id",
            "fingerprint",
            name="uq_dashboard_dismissal_version",
        ),
        Index(
            "ix_dashboard_dismissal_user_entity", "user_id", "entity_type", "entity_id"
        ),
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(32), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(200), nullable=False)
    dismissed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
