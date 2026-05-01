"""Add unique constraint for contractor INN.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "uq_contractors_inn"


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    duplicate_count = bind.scalar(
        sa.text(
            """
            SELECT count(*)
            FROM (
                SELECT inn
                FROM contractors
                WHERE inn IS NOT NULL
                GROUP BY inn
                HAVING count(*) > 1
            ) duplicates
            """
        )
    )
    if duplicate_count:
        raise ValueError(
            "Cannot add unique constraint uq_contractors_inn: "
            f"contractors contains {duplicate_count} duplicate non-null INN value(s)."
        )

    op.create_unique_constraint(CONSTRAINT_NAME, "contractors", ["inn"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(CONSTRAINT_NAME, "contractors", type_="unique")
