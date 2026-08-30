# Primary-market evidence

Primary-market facts are imported only from explicitly supplied official NSE exports.  No NSE or IPO website is scraped and no automatic live primary-market source is configured.

`PrimaryMarketIssue` preserves issue type, price/size metadata, issue and listing dates, primary provenance, official document references, and the distinct fresh-issue and OFS amounts.  OFS is factual seller/liquidity evidence, not a bearish classification.

Subscription snapshots preserve their source semantic: `BID_POSITION`, `CONFIRMED_BID`, `FINAL_SUBSCRIPTION`, or `UNKNOWN`.  Bid-position data is never presented as final subscription.  Both issue and subscription history are point-in-time eligible only after publication/receipt.

Listing outcomes derive only from canonical stored market-data evidence after listing.  Aggregates are factual coverage-aware counts, amount mix, eligible subscription values, and listing premiums.  The existing Market Extremes contract receives an `IPOIntensityObservation`; IPO activity alone cannot confirm a top, create EXIT/SELL, or classify Euphoria.
