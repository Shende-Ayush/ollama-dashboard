"""model download jobs

Revision ID: 20260428_0002
Revises: 20260419_0001
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # model_download_jobs table
    op.alter_column(
        "model_download_jobs",
        "completed_bytes",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )

    op.alter_column(
        "model_download_jobs",
        "total_bytes",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )

    # model_instances table
    op.alter_column(
        "model_instances",
        "memory_usage_mb",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade():
    print("Downgrade not supported for model_download_jobs due to potential data loss when converting BigInteger back to Integer.")