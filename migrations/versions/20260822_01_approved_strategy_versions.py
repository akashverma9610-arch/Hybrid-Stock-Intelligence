"""initial PostgreSQL approved strategy-version immutable storage"""

from alembic import op
import sqlalchemy as sa


revision = "20260822_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approved_strategy_versions",
        sa.Column("approved_id", sa.Text(), primary_key=True),
        sa.Column("strategy_id", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("parent_approved_id", sa.Text(), nullable=True),
        sa.Column("proposal_id", sa.Text(), nullable=False),
        sa.Column("review_id", sa.Text(), nullable=False),
        sa.Column("candidate_id", sa.Text(), nullable=False),
        sa.Column("config_fingerprints", sa.JSON(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("methodology_notes", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False, unique=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.CheckConstraint("status IN ('APPROVED', 'SUSPENDED')", name="approved_strategy_versions_status_check"),
        sa.UniqueConstraint("strategy_id", "version", name="approved_strategy_versions_strategy_version_unique"),
    )


def downgrade() -> None:
    op.drop_table("approved_strategy_versions")
