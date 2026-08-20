"""Add CandidateProfile and update Job

Revision ID: d4d778fd4d42
Revises: 0006
Create Date: 2026-08-19 16:51:07.107123+00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4d778fd4d42'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create candidate_profiles
    op.create_table(
        'candidate_profiles',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('identity', sa.JSON(), nullable=False),
        sa.Column('location', sa.JSON(), nullable=False),
        sa.Column('employment', sa.JSON(), nullable=False),
        sa.Column('work_authorization', sa.JSON(), nullable=False),
        sa.Column('education', sa.JSON(), nullable=False),
        sa.Column('experience', sa.JSON(), nullable=False),
        sa.Column('skills', sa.JSON(), nullable=False),
        sa.Column('projects', sa.JSON(), nullable=False),
        sa.Column('certifications', sa.JSON(), nullable=False),
        sa.Column('preferences', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('tenant_id', sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # 2. Update jobs table
    # SQLite does not support ALTER TABLE ADD COLUMN for some types easily with alembic without batch, but since this is fresh db, we can just add columns. 
    # Actually wait! The DB is wiped. But in a real scenario we use batch. Let's use batch for safety.
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('country', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('city', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('application_url', sa.String(length=2000), nullable=True))
        batch_op.add_column(sa.Column('responsibilities', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('requirements', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('salary', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('employment_type', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('work_model', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('seniority', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('gcc_eligibility', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('raw_data', sa.JSON(), nullable=True))

    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('audit_metadata', sa.JSON(), nullable=True))

    with op.batch_alter_table('resumes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('audit_metadata', sa.JSON(), nullable=True))

def downgrade() -> None:
    pass
