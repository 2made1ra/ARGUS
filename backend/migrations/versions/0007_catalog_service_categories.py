"""Add catalog service category enrichment fields.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("price_items", sa.Column("service_category", sa.Text()))
    op.add_column("price_items", sa.Column("service_category_confidence", sa.Float()))
    op.add_column("price_items", sa.Column("service_category_source", sa.Text()))
    op.add_column("price_items", sa.Column("service_category_reason", sa.Text()))
    op.add_column(
        "price_items",
        sa.Column(
            "category_enrichment_status",
            sa.Text(),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
    )
    op.add_column("price_items", sa.Column("category_enrichment_error", sa.Text()))
    op.add_column(
        "price_items",
        sa.Column("category_enriched_at", sa.TIMESTAMP(timezone=True)),
    )
    op.add_column("price_items", sa.Column("category_enrichment_model", sa.Text()))
    op.add_column(
        "price_items",
        sa.Column("category_enrichment_prompt_version", sa.Text()),
    )
    op.create_index(
        "ix_price_items_service_category",
        "price_items",
        ["service_category"],
    )
    op.create_index(
        "ix_price_items_category_enrichment_status",
        "price_items",
        ["category_enrichment_status"],
    )
    op.execute(
        sa.text(
            """
            UPDATE price_items
            SET
                service_category = CASE
                    WHEN category_normalized IN ('звук', 'аудио') THEN 'звук'
                    WHEN category_normalized IN ('свет') THEN 'свет'
                    WHEN category_normalized IN ('питание', 'еда', 'кейтеринг')
                        THEN 'кейтеринг'
                    WHEN category_normalized IN ('проживание') THEN 'проживание'
                    WHEN category_normalized IN ('мебель') THEN 'мебель'
                    WHEN category_normalized IN ('декор') THEN 'декор'
                    WHEN category_normalized IN ('персонал') THEN 'персонал'
                    WHEN category_normalized IN ('логистика') THEN 'логистика'
                    WHEN category_normalized IN ('площадка') THEN 'площадка'
                    WHEN category_normalized IN ('полиграфия') THEN 'полиграфия'
                    ELSE service_category
                END,
                service_category_confidence = 1.0,
                service_category_source = 'deterministic',
                service_category_reason = 'source_category_alias',
                category_enrichment_status = 'enriched',
                category_enriched_at = now(),
                catalog_index_status = 'pending',
                indexed_at = NULL
            WHERE category_normalized IN (
                'звук',
                'аудио',
                'свет',
                'питание',
                'еда',
                'кейтеринг',
                'проживание',
                'мебель',
                'декор',
                'персонал',
                'логистика',
                'площадка',
                'полиграфия'
            )
            """
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_price_items_category_enrichment_status",
        table_name="price_items",
    )
    op.drop_index("ix_price_items_service_category", table_name="price_items")
    op.drop_column("price_items", "category_enrichment_prompt_version")
    op.drop_column("price_items", "category_enrichment_model")
    op.drop_column("price_items", "category_enriched_at")
    op.drop_column("price_items", "category_enrichment_error")
    op.drop_column("price_items", "category_enrichment_status")
    op.drop_column("price_items", "service_category_reason")
    op.drop_column("price_items", "service_category_source")
    op.drop_column("price_items", "service_category_confidence")
    op.drop_column("price_items", "service_category")
