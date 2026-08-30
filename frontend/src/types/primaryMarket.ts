export interface PrimaryMarketItem {
  id: string;
  issueName: string;
  issueType: 'MAINBOARD_IPO' | 'SME_IPO' | 'FPO' | 'OFS' | 'RIGHTS_ISSUE';
  openDate: string | null;
  closeDate: string | null;
  listingDate: string | null;
  priceBand: string | null;
  issueSizeCr: number | null;
  freshIssueCr: number | null;
  ofsSizeCr: number | null;
  overallSubscriptionTimes: number | null;
  qibSubscriptionTimes: number | null;
  niiSubscriptionTimes: number | null;
  retailSubscriptionTimes: number | null;
  gmpEstimatedPremiumPct: number | null;
  listingPrice: number | null;
  listingGainsPct: number | null;
  currentMarketPrice: number | null;
  postListingReturnPct: number | null;
  sector: string;
  status: 'UPCOMING' | 'OPEN' | 'CLOSED' | 'LISTED';
}

export interface PrimaryMarketData {
  openIssues: PrimaryMarketItem[];
  upcomingIssues: PrimaryMarketItem[];
  recentlyListed: PrimaryMarketItem[];
}
