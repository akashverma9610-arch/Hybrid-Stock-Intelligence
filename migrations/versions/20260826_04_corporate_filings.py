"""corporate filings

Revision ID: 20260826_04
Revises: 20260823_03
"""

from alembic import op
import sqlalchemy as sa


revision = "20260826_04"
down_revision = "20260823_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corporate_filings",
        sa.Column("filing_id", sa.String(), primary_key=True),
        sa.Column("instrument_id", sa.String(), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("filing_type", sa.String(), nullable=False),
        sa.Column("announced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("source_reference", sa.String(), nullable=True),
        sa.Column("revision_of_filing_id", sa.String(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
    )
    op.create_index("ix_filings_instrument_announced", "corporate_filings", ["instrument_id", "announced_at"])
    op.create_index("ix_filings_type_announced", "corporate_filings", ["filing_type", "announced_at"])
    op.create_index("ix_filings_exchange_announced", "corporate_filings", ["exchange", "announced_at"])
    op.create_index("ix_filings_source_reference", "corporate_filings", ["source", "source_reference"])
    op.create_index("ix_filings_revision", "corporate_filings", ["revision_of_filing_id"])


def downgrade() -> None:
    for name in ("ix_filings_revision", "ix_filings_source_reference", "ix_filings_exchange_announced", "ix_filings_type_announced", "ix_filings_instrument_announced"):
        op.drop_index(name, table_name="corporate_filings")
    op.drop_table("corporate_filings")
