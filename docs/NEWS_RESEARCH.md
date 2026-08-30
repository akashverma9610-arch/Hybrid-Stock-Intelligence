# News and research evidence

News is optional secondary evidence.  Primary exchange and issuer filings remain the factual source of truth; a GNews article can provide publisher-attributed context and may be factually linked to a filing, but never replaces it.

`NewsArticleEvidence` retains only licensed/provider-returned metadata: title, optional description snippet, URL, publisher metadata, timestamps, source quality, entity match, and provenance.  The service never downloads, stores, or scrapes an article page.

Point-in-time use requires both `published_at` and `received_at` to be no later than the requested `as_of` timestamp.  Ambiguous matches remain visible without a fabricated instrument match.  Deduplication uses provider article identity when present and URL otherwise; different publishers covering the same event remain distinct.

The optional GNews Search provider defaults to `country=in` and `lang=en`, but those filters describe publication filtering, not proof of event scope.  Plan timeliness can be delayed/development-only; `READY` requires explicit validation.  GNews has no fundamentals feed and no silent fallback exists.

The research input adapter maps factual metadata into the established `ResearchSnapshot` and catalyst-clock boundaries.  It supplies no expectation/consensus, materiality score, decision score, signal, or regime instruction.
