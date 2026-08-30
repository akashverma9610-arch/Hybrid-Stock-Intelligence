"""immutable versioned core API read snapshots"""
from alembic import op
import sqlalchemy as sa
revision="20260822_02"
down_revision="20260822_01"
branch_labels=None
depends_on=None
def upgrade()->None:
    op.create_table("core_api_snapshots",sa.Column("snapshot_id",sa.Text(),primary_key=True),sa.Column("family",sa.String(48),nullable=False),sa.Column("schema_version",sa.String(16),nullable=False),sa.Column("record_type",sa.String(128),nullable=False),sa.Column("fingerprint",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("payload_json",sa.JSON(),nullable=False),sa.UniqueConstraint("family","fingerprint",name="core_api_snapshots_family_fingerprint_unique"))
    op.create_index("core_api_snapshots_family_created_idx","core_api_snapshots",["family","created_at","snapshot_id"])
def downgrade()->None:
    op.drop_index("core_api_snapshots_family_created_idx",table_name="core_api_snapshots")
    op.drop_table("core_api_snapshots")
