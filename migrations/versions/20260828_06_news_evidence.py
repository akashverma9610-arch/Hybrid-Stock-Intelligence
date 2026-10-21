"""News evidence metadata table (no credentials or article-page content)."""
revision = "20260828_06_news_evidence"
down_revision = "20260827_05"
branch_labels = None
depends_on = None

def upgrade():
    from alembic import op
    op.execute("""CREATE TABLE IF NOT EXISTS news_evidence (article_id TEXT PRIMARY KEY, source_provider TEXT NOT NULL, provider_article_id TEXT, url TEXT NOT NULL, published_at TIMESTAMPTZ NOT NULL, received_at TIMESTAMPTZ NOT NULL, instrument_ids_json JSONB NOT NULL, sectors_json JSONB NOT NULL, payload_json JSONB NOT NULL, UNIQUE(source_provider,url))""")
    op.execute("CREATE INDEX IF NOT EXISTS ix_news_evidence_published ON news_evidence(published_at DESC,article_id DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_news_evidence_provider_provider_id ON news_evidence(source_provider,provider_article_id)")
def downgrade():
    from alembic import op
    op.execute("DROP TABLE IF EXISTS news_evidence")
