"""Phase 20A.3 operational UX persistence.

Revision ID: d20a3f01
Revises: c4f19a2b7d30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "d20a3f01"
down_revision: Union[str, None] = "c4f19a2b7d30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("resumes") as batch_op:
        batch_op.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "dashboard_dismissals",
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=32), nullable=False),
        sa.Column("fingerprint", sa.String(length=200), nullable=False),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "entity_type", "entity_id", "fingerprint", name="uq_dashboard_dismissal_version"),
    )
    op.create_index("ix_dashboard_dismissal_user_entity", "dashboard_dismissals", ["user_id", "entity_type", "entity_id"])
    op.create_index("ix_dashboard_dismissals_user_id", "dashboard_dismissals", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_dashboard_dismissals_user_id", table_name="dashboard_dismissals")
    op.drop_index("ix_dashboard_dismissal_user_entity", table_name="dashboard_dismissals")
    op.drop_table("dashboard_dismissals")
    with op.batch_alter_table("resumes") as batch_op:
        batch_op.drop_column("archived_at")
