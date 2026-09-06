"""Series-aware source identity; retain all pre-migration observations.

Revision ID: 20260906_10
Revises: 20260830_09
"""
from alembic import op
import sqlalchemy as sa

from app.market_data.historical import _bar_from_mapping
from app.market_data.nse_udiff_archive_verification import UdiffArchiveVerifier
from app.market_data.nse_udiff_source_identity import observation_key
from app.storage.core_api_snapshot_repository import snapshot_json_from

revision = "20260906_10"
down_revision = "20260830_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT bar_id FROM historical_bar_observations WHERE provider_identity='nse_udiff_official' GROUP BY bar_id HAVING count(*)>1 LIMIT 1")).first():
        raise ValueError("UDIFF_MIGRATION_AMBIGUOUS_BAR_IDS")
    # Existing PostgreSQL transactions provide atomic DDL/copy/PK replacement.
    op.execute("CREATE TABLE historical_observations_pre_udiff_v1 AS SELECT * FROM historical_bar_observations")
    op.add_column("historical_bar_observations", sa.Column("source_observation_identity", sa.Text(), nullable=False, server_default=""))

    def load(identifier):
        raw = connection.execute(sa.text("SELECT payload_json FROM core_api_snapshots WHERE snapshot_id=:id"), {"id": identifier}).scalar_one()
        return snapshot_json_from(raw).payload

    verify = UdiffArchiveVerifier(load)
    # Keyset pages bound memory and avoid invalidating an active streaming cursor.
    last = ""
    while True:
        rows = connection.execute(sa.text("SELECT * FROM historical_bar_observations WHERE provider_identity='nse_udiff_official' AND bar_id>:last ORDER BY bar_id LIMIT 1000"), {"last": last}).mappings().all()
        if not rows:
            break
        for row in rows:
            old = dict(row)
            old.pop("source_observation_identity")
            bar = _bar_from_mapping(old)
            verify(bar)
            connection.execute(sa.text("UPDATE historical_bar_observations SET source_observation_identity=:identity WHERE instrument_id=:instrument_id AND timeframe=:timeframe AND start_time=:start_time AND end_time=:end_time AND provider_identity=:provider_identity"), {**old, "identity": observation_key(bar)})
        last = rows[-1]["bar_id"]
    if connection.execute(sa.text("SELECT 1 FROM historical_bar_observations WHERE provider_identity='nse_udiff_official' AND source_observation_identity='' LIMIT 1")).first():
        raise ValueError("UDIFF_MIGRATION_UNVERIFIED_SOURCE_ROW")
    op.drop_constraint("historical_bar_observations_identity", "historical_bar_observations", type_="primary")
    op.create_primary_key("historical_bar_observations_identity", "historical_bar_observations", ["instrument_id", "timeframe", "start_time", "end_time", "provider_identity", "source_observation_identity"])


def downgrade() -> None:
    raise RuntimeError("UDIFF_SERIES_EVIDENCE_PRESERVING_FORWARD_MIGRATION_REQUIRED")
