"""Scheduled opportunity-monitoring persistence models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin, UUIDPrimaryKeyMixin


class MonitoringSchedule(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "monitoring_schedules"

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(2000), nullable=False)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    match_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=.75)
    max_preparations_per_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    runs: Mapped[list["MonitoringRun"]] = relationship(
        back_populates="schedule", cascade="all, delete-orphan"
    )


class MonitoringRun(UUIDPrimaryKeyMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "monitoring_runs"

    schedule_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("monitoring_schedules.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    duration: Mapped[float | None] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
    jobs_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_new: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_eligible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    jobs_selected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    schedule: Mapped[MonitoringSchedule] = relationship(back_populates="runs")
