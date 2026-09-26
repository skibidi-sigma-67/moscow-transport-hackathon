"""Add status and error_text to prediction_logs

Revision ID: bd89d2bce10a
Revises: ad78c1abd009
Create Date: 2026-09-26 19:57:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd89d2bce10a"
down_revision: str | Sequence[str] | None = "ad78c1abd009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prediction_logs",
        sa.Column("status", sa.String(length=50), server_default="OK", nullable=False),
    )
    op.add_column(
        "prediction_logs",
        sa.Column("error_text", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prediction_logs", "error_text")
    op.drop_column("prediction_logs", "status")
