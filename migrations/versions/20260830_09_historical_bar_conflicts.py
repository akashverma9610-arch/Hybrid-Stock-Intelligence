"""append-only same-provider historical bar conflict artifacts

Revision ID: 20260830_09
Revises: 20260830_08
"""
from alembic import op
import sqlalchemy as sa


revision = "20260830_09"
down_revision = "20260830_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_bar_conflicts",
        sa.Column("conflict_fingerprint", sa.String(64), primary_key=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("historical_bar_conflicts")
