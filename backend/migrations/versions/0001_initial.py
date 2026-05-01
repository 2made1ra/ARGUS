"""Initial PostgreSQL schema.

Revision ID: 0001
Revises:
Create Date: 2026-05-01

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "contractors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.Text()),
        sa.Column("normalized_key", sa.Text(), unique=True),
        sa.Column("inn", sa.Text()),
        sa.Column("kpp", sa.Text()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "contractor_raw_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("raw_name", sa.Text()),
        sa.Column("inn", sa.Text()),
        sa.Column(
            "contractor_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contractors.id", ondelete="CASCADE"),
        ),
        sa.Column("confidence", sa.Float()),
    )
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "contractor_entity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contractors.id", ondelete="CASCADE"),
        ),
        sa.Column("title", sa.Text()),
        sa.Column("file_path", sa.Text()),
        sa.Column("content_type", sa.Text()),
        sa.Column("document_kind", sa.Text()),
        sa.Column("doc_type", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("partial_extraction", sa.Boolean()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
        ),
        sa.Column("chunk_index", sa.Integer()),
        sa.Column("text", sa.Text()),
        sa.Column("page_start", sa.Integer()),
        sa.Column("page_end", sa.Integer()),
        sa.Column("section_type", sa.Text()),
        sa.Column("chunk_summary", sa.Text()),
    )
    op.create_table(
        "extracted_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("fields", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "document_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            unique=True,
        ),
        sa.Column("summary", sa.Text()),
        sa.Column("key_points", postgresql.ARRAY(sa.Text())),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("document_summaries")
    op.drop_table("extracted_fields")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("contractor_raw_mappings")
    op.drop_table("contractors")
