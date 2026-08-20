"""User account model — the tenant root."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An authenticated account. Owns all tenant-scoped rows via ``user_id``."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Soft-delete (D9): hidden immediately, purged after a grace period in Phase 4.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    profile: Mapped["CandidateProfile"] = relationship(  # type: ignore # noqa: F821
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"
