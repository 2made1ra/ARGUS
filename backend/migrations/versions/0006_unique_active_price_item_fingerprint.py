"""Make active price item fingerprints unique.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index("ix_price_items_row_fingerprint_active", table_name="price_items")
    op.create_index(
        "ix_price_items_row_fingerprint_active",
        "price_items",
        ["row_fingerprint"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_price_items_row_fingerprint_active", table_name="price_items")
    op.create_index(
        "ix_price_items_row_fingerprint_active",
        "price_items",
        ["row_fingerprint"],
        postgresql_where=sa.text("is_active = true"),
    )
