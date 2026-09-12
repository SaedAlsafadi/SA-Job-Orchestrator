"""Phase 20C structured-output telemetry.

Revision ID: f31a20c
Revises: d20a3f01
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f31a20c"
down_revision: Union[str, None] = "d20a3f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PURPOSES = (
    "match_deep", "job_requirement_analysis", "match_explanation", "cv_tailor",
    "cv_review", "application_qa", "application_email", "application_answers",
    "job_normalization", "route_resolution",
)


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for purpose in _PURPOSES:
            op.execute(f"ALTER TYPE llm_purpose ADD VALUE IF NOT EXISTS '{purpose}'")
    with op.batch_alter_table("llm_usage") as batch:
        batch.alter_column("cost_usd", existing_type=sa.Float(), nullable=True)
        batch.add_column(sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"))
        batch.add_column(sa.Column("parse_failure", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("llm_usage") as batch:
        batch.drop_column("parse_failure")
        batch.drop_column("attempt")
        batch.alter_column("cost_usd", existing_type=sa.Float(), nullable=False, server_default="0")
