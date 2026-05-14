"""Add catalog import job progress table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "catalog_import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "stage_progress_percent",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "invalid_row_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("index_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("indexing_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="ck_catalog_import_jobs_progress_percent",
        ),
        sa.CheckConstraint(
            "stage_progress_percent >= 0 AND stage_progress_percent <= 100",
            name="ck_catalog_import_jobs_stage_progress_percent",
        ),
    )
    op.create_index(
        "ix_catalog_import_jobs_status",
        "catalog_import_jobs",
        ["status"],
    )
    op.create_index(
        "ix_catalog_import_jobs_created_at",
        "catalog_import_jobs",
        ["created_at"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_catalog_import_jobs_created_at", table_name="catalog_import_jobs")
    op.drop_index("ix_catalog_import_jobs_status", table_name="catalog_import_jobs")
    op.drop_table("catalog_import_jobs")
