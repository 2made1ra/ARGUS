"""Add catalog price item import tables.

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "price_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("file_sha256", sa.Text(), nullable=True),
        sa.Column(
            "schema_version",
            sa.Text(),
            nullable=False,
            server_default="prices_csv_v1",
        ),
        sa.Column(
            "embedding_template_version",
            sa.Text(),
            nullable=False,
            server_default="prices_v1",
        ),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "invalid_row_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index(
        "ux_price_imports_file_sha256_not_null",
        "price_imports",
        ["file_sha256"],
        unique=True,
        postgresql_where=sa.text("file_sha256 is not null"),
    )

    op.create_table(
        "price_import_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw", postgresql.JSONB(), nullable=False),
        sa.Column("normalized", postgresql.JSONB(), nullable=True),
        sa.Column("legacy_embedding_dim", sa.Integer(), nullable=True),
        sa.Column(
            "legacy_embedding_present",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "validation_warnings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("price_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["price_imports.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_price_import_rows_import_batch_id",
        "price_import_rows",
        ["import_batch_id"],
    )
    op.create_index(
        "ix_price_import_rows_price_item_id",
        "price_import_rows",
        ["price_item_id"],
    )

    op.create_table(
        "price_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("category_normalized", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("unit_normalized", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column("section", sa.Text(), nullable=True),
        sa.Column("section_normalized", sa.Text(), nullable=True),
        sa.Column("supplier", sa.Text(), nullable=True),
        sa.Column("has_vat", sa.Text(), nullable=True),
        sa.Column("vat_mode", sa.Text(), nullable=True),
        sa.Column("supplier_inn", sa.Text(), nullable=True),
        sa.Column("supplier_city", sa.Text(), nullable=True),
        sa.Column("supplier_city_normalized", sa.Text(), nullable=True),
        sa.Column("supplier_phone", sa.Text(), nullable=True),
        sa.Column("supplier_email", sa.Text(), nullable=True),
        sa.Column("supplier_status", sa.Text(), nullable=True),
        sa.Column("supplier_status_normalized", sa.Text(), nullable=True),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_import_row_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("row_fingerprint", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("superseded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("embedding_text", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.Text(), nullable=False),
        sa.Column(
            "embedding_template_version",
            sa.Text(),
            nullable=False,
            server_default="prices_v1",
        ),
        sa.Column("catalog_index_status", sa.Text(), nullable=False),
        sa.Column("embedding_error", sa.Text(), nullable=True),
        sa.Column("indexing_error", sa.Text(), nullable=True),
        sa.Column("indexed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "legacy_embedding_present",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("legacy_embedding_dim", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["price_imports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_import_row_id"],
            ["price_import_rows.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_foreign_key(
        "fk_price_import_rows_price_item_id_price_items",
        "price_import_rows",
        "price_items",
        ["price_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_price_items_row_fingerprint_active",
        "price_items",
        ["row_fingerprint"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "ix_price_items_catalog_index_status",
        "price_items",
        ["catalog_index_status"],
    )
    op.create_index(
        "ix_price_items_supplier_city_normalized",
        "price_items",
        ["supplier_city_normalized"],
    )
    op.create_index(
        "ix_price_items_category_normalized",
        "price_items",
        ["category_normalized"],
    )
    op.create_index(
        "ix_price_items_supplier_status_normalized",
        "price_items",
        ["supplier_status_normalized"],
    )
    op.create_index("ix_price_items_supplier_inn", "price_items", ["supplier_inn"])

    op.create_table(
        "price_item_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("price_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_kind",
            sa.Text(),
            nullable=False,
            server_default="csv_import",
        ),
        sa.Column("import_batch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_file_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("price_import_row_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_text", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["price_item_id"],
            ["price_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["import_batch_id"],
            ["price_imports.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["price_import_row_id"],
            ["price_import_rows.id"],
            ondelete="SET NULL",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("price_item_sources")
    op.drop_index("ix_price_items_supplier_inn", table_name="price_items")
    op.drop_index(
        "ix_price_items_supplier_status_normalized",
        table_name="price_items",
    )
    op.drop_index("ix_price_items_category_normalized", table_name="price_items")
    op.drop_index(
        "ix_price_items_supplier_city_normalized",
        table_name="price_items",
    )
    op.drop_index("ix_price_items_catalog_index_status", table_name="price_items")
    op.drop_index("ix_price_items_row_fingerprint_active", table_name="price_items")
    op.drop_constraint(
        "fk_price_import_rows_price_item_id_price_items",
        "price_import_rows",
        type_="foreignkey",
    )
    op.drop_table("price_items")
    op.drop_index(
        "ix_price_import_rows_price_item_id",
        table_name="price_import_rows",
    )
    op.drop_index(
        "ix_price_import_rows_import_batch_id",
        table_name="price_import_rows",
    )
    op.drop_table("price_import_rows")
    op.drop_index(
        "ux_price_imports_file_sha256_not_null",
        table_name="price_imports",
    )
    op.drop_table("price_imports")
