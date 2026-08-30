"""Primary-market immutable facts and subscription history."""
revision="20260829_07_primary_market";down_revision="20260828_06_news_evidence";branch_labels=None;depends_on=None
def upgrade():
 from alembic import op
 op.execute("CREATE TABLE IF NOT EXISTS primary_market_issues(issue_id TEXT PRIMARY KEY,open_date TIMESTAMPTZ,listing_date TIMESTAMPTZ,sector TEXT,issue_type TEXT,issuer TEXT,payload JSONB NOT NULL)")
 op.execute("CREATE TABLE IF NOT EXISTS primary_market_subscriptions(snapshot_id TEXT PRIMARY KEY,issue_id TEXT NOT NULL,observed_at TIMESTAMPTZ NOT NULL,category TEXT NOT NULL,payload JSONB NOT NULL)")
 op.execute("CREATE TABLE IF NOT EXISTS primary_market_listing_outcomes(issue_id TEXT PRIMARY KEY,observed_at TIMESTAMPTZ NOT NULL,payload JSONB NOT NULL)")
def downgrade():
 from alembic import op
 op.execute("DROP TABLE IF EXISTS primary_market_listing_outcomes;DROP TABLE IF EXISTS primary_market_subscriptions;DROP TABLE IF EXISTS primary_market_issues")
