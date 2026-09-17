"""Add opt-in P1 lifecycle concurrency indexes; no production activation."""
from alembic import op
import sqlalchemy as sa

revision = "20260917_11"
down_revision = "20260906_10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "p1_signal_lifecycle_batch_index",
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("core_api_snapshots.snapshot_id"), primary_key=True),
        sa.Column("slot_key", sa.Text(), nullable=False),
        sa.Column("input_key", sa.Text(), nullable=False),
        sa.Column("accepted_cutoff", sa.Text(), nullable=False),
        sa.UniqueConstraint("slot_key", "input_key"),
        sa.UniqueConstraint("slot_key", "accepted_cutoff"),
    )
    op.create_table(
        "p1_signal_lifecycle_heads",
        sa.Column("slot_key", sa.Text(), primary_key=True),
        sa.Column("batch_id", sa.Text(), sa.ForeignKey("core_api_snapshots.snapshot_id"), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("accepted_cutoff", sa.Text(), nullable=False),
        sa.Column("current_lifetime_id", sa.Text()),
    )


def downgrade():
    op.drop_table("p1_signal_lifecycle_heads")
    op.drop_table("p1_signal_lifecycle_batch_index")
