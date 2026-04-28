"""model download jobs

Revision ID: 20260428_0002
Revises: 20260419_0001
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_download_jobs",
        sa.Column("request_id", sa.String(length=64), primary_key=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("percent", sa.Float(), nullable=False),
        sa.Column("completed_bytes", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.Integer(), nullable=False),
        sa.Column("speed_mbps", sa.Float(), nullable=False),
        sa.Column("stop_requested", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_model_download_jobs_model_name", "model_download_jobs", ["model_name"], unique=False)
    op.create_index("ix_model_download_jobs_status", "model_download_jobs", ["status"], unique=False)
    op.create_index("ix_model_download_jobs_started_at", "model_download_jobs", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_model_download_jobs_started_at", table_name="model_download_jobs")
    op.drop_index("ix_model_download_jobs_status", table_name="model_download_jobs")
    op.drop_index("ix_model_download_jobs_model_name", table_name="model_download_jobs")
    op.drop_table("model_download_jobs")
