"""canonical financial facts

Revision ID: 20260827_05
Revises: 20260826_04
"""
from alembic import op
import sqlalchemy as sa
revision="20260827_05"; down_revision="20260826_04"; branch_labels=None; depends_on=None
def upgrade() -> None:
    op.create_table("financial_facts",sa.Column("fact_id",sa.String(),primary_key=True),sa.Column("instrument_id",sa.String(),nullable=False),sa.Column("metric",sa.String(),nullable=False),sa.Column("value_numeric",sa.Numeric(),nullable=False),sa.Column("period_end",sa.DateTime(timezone=True),nullable=False),sa.Column("period_type",sa.String(),nullable=False),sa.Column("statement_scope",sa.String(),nullable=False),sa.Column("fact_kind",sa.String(),nullable=False),sa.Column("source",sa.String(),nullable=False),sa.Column("source_reference",sa.String()),sa.Column("filing_id",sa.String()),sa.Column("published_at",sa.DateTime(timezone=True),nullable=False),sa.Column("received_at",sa.DateTime(timezone=True),nullable=False),sa.Column("payload_json",sa.JSON(),nullable=False))
    op.create_index("ix_financial_facts_metric_period","financial_facts",["instrument_id","metric","period_end"]);op.create_index("ix_financial_facts_period","financial_facts",["instrument_id","period_end"]);op.create_index("ix_financial_facts_filing","financial_facts",["filing_id","source","source_reference"])
def downgrade() -> None:
    for name in ("ix_financial_facts_filing","ix_financial_facts_period","ix_financial_facts_metric_period"):op.drop_index(name,table_name="financial_facts")
    op.drop_table("financial_facts")
