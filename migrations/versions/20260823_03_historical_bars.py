"""dedicated normalized historical OHLCV storage"""
from alembic import op
import sqlalchemy as sa

revision = "20260823_03"
down_revision = "20260822_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "historical_bars",
        sa.Column("instrument_id", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("bar_id", sa.Text(), nullable=False),
        sa.Column("open", sa.Numeric(), nullable=False), sa.Column("high", sa.Numeric(), nullable=False),
        sa.Column("low", sa.Numeric(), nullable=False), sa.Column("close", sa.Numeric(), nullable=False),
        sa.Column("volume", sa.BigInteger()), sa.Column("turnover", sa.Numeric()), sa.Column("trade_count", sa.BigInteger()),
        sa.Column("adjustment_status", sa.String(16), nullable=False),
        sa.Column("instrument_json", sa.JSON(), nullable=False), sa.Column("provenance_json", sa.JSON(), nullable=False),
        sa.Column("quality", sa.String(16), nullable=False), sa.Column("warnings_json", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("instrument_id", "timeframe", "start_time", "end_time", name="historical_bars_identity"),
    )
    op.create_index("historical_bars_instrument_time_start_idx", "historical_bars", ["instrument_id", "timeframe", "start_time"])


def downgrade() -> None:
    op.drop_index("historical_bars_instrument_time_start_idx", table_name="historical_bars")
    op.drop_table("historical_bars")
