"""append-only provider-versioned historical bar observations

Revision ID: 20260830_08
Revises: 20260829_07
"""
from alembic import op
import sqlalchemy as sa


revision = "20260830_08"
down_revision = "20260829_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_bar_observations",
        sa.Column("instrument_id", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_identity", sa.String(128), nullable=False),
        sa.Column("bar_id", sa.Text(), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False), sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False), sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.BigInteger()), sa.Column("turnover", sa.Numeric()), sa.Column("trade_count", sa.BigInteger()),
        sa.Column("adjustment_status", sa.String(16), nullable=False),
        sa.Column("instrument_json", sa.JSON(), nullable=False), sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("quality", sa.String(16), nullable=False), sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("instrument_id", "timeframe", "start_time", "end_time", "provider_identity", name="historical_bar_observations_identity"),
    )
    op.create_index("historical_bar_observations_time_idx", "historical_bar_observations", ["instrument_id", "timeframe", "start_time", "end_time"])
    # The prior table is intentionally retained.  PostgreSQL's JSONB provider
    # field is deterministic provenance; rows without it become explicit
    # unknown legacy source rather than being guessed.
    op.execute("""
        INSERT INTO historical_bar_observations
        (instrument_id,timeframe,start_time,end_time,provider_identity,bar_id,open,high,low,close,volume,turnover,trade_count,adjustment_status,instrument_json,provenance_json,quality,warnings_json)
        SELECT instrument_id,timeframe,start_time,end_time,
               COALESCE(NULLIF(LOWER(provenance_json->>'provider'), ''), 'unknown_existing_source'),
               bar_id,open,high,low,close,volume,turnover,trade_count,adjustment_status,instrument_json,provenance_json,quality,warnings_json
        FROM historical_bars
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    # Legacy ``historical_bars`` stays untouched throughout upgrade, so this
    # rollback only removes the provider-versioned projection.
    op.drop_index("historical_bar_observations_time_idx", table_name="historical_bar_observations")
    op.drop_table("historical_bar_observations")
