"""Phase 19 Application Packages

Revision ID: c4f19a2b7d30
Revises: 68fdbbe17245
Create Date: 2026-09-07 10:05:00.000000+00:00

Creates the immutable, version-locked ``application_packages`` table and adds the
package-binding columns to ``application_approvals`` (nullable — existing approvals,
which bind to runs only, remain valid untouched).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4f19a2b7d30'
down_revision: Union[str, None] = '68fdbbe17245'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'application_packages',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('user_id', sa.String(length=32), nullable=False),
        sa.Column('application_id', sa.String(length=32), nullable=False),
        sa.Column('job_id', sa.String(length=32), nullable=False),
        sa.Column('route_id', sa.String(length=32), nullable=True),
        sa.Column('resume_id', sa.String(length=32), nullable=True),
        sa.Column('cover_letter_key', sa.String(length=500), nullable=True),
        sa.Column('cover_letter_text', sa.Text(), nullable=True),
        sa.Column('email_to', sa.String(length=320), nullable=True),
        sa.Column('email_subject', sa.String(length=500), nullable=True),
        sa.Column('email_body', sa.Text(), nullable=True),
        sa.Column('attachment_keys', sa.JSON(), nullable=True),
        sa.Column('answers', sa.JSON(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False),
        sa.Column('qa_verdict', sa.Enum('pass', 'warning', 'blocked', name='qa_verdict'), nullable=True),
        sa.Column('qa_issues', sa.JSON(), nullable=True),
        sa.Column('qa_model', sa.String(length=100), nullable=True),
        sa.Column('approval_id', sa.String(length=32), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column(
            'send_state',
            sa.Enum('pending', 'sent', 'failed', 'unknown', name='email_send_state'),
            nullable=True,
        ),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('message_id', sa.String(length=500), nullable=True),
        sa.Column('provider_response', sa.Text(), nullable=True),
        sa.Column('sender_address', sa.String(length=320), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['route_id'], ['application_routes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('application_packages', schema=None) as batch_op:
        batch_op.create_index('ix_package_application', ['application_id'], unique=False)
        batch_op.create_index('ix_package_current', ['application_id', 'is_current'], unique=False)
        batch_op.create_index('ix_application_packages_user_id', ['user_id'], unique=False)

    with op.batch_alter_table('application_approvals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('package_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('package_version', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('package_hash', sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('application_approvals', schema=None) as batch_op:
        batch_op.drop_column('package_hash')
        batch_op.drop_column('package_version')
        batch_op.drop_column('package_id')

    with op.batch_alter_table('application_packages', schema=None) as batch_op:
        batch_op.drop_index('ix_application_packages_user_id')
        batch_op.drop_index('ix_package_current')
        batch_op.drop_index('ix_package_application')

    op.drop_table('application_packages')

    # SQLite cannot easily drop enum types; PostgreSQL cleanup for the two new enums.
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        sa.Enum(name='qa_verdict').drop(bind, checkfirst=True)
        sa.Enum(name='email_send_state').drop(bind, checkfirst=True)
