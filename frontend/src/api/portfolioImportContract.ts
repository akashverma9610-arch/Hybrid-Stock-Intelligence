/** Review-only boundary for the existing screenshot API. No HTTP or persistence. */
export interface ReviewedScreenshotHolding {
  rowId: string;
  instrumentId: string | null;
  symbol: string | null;
  quantity: string | null;
  averagePrice: string | null;
  include: boolean;
}

export interface ScreenshotCandidate extends Omit<ReviewedScreenshotHolding, 'include'> {
  instrumentName: string | null;
  currentPrice: string | null;
  extractionConfidence: string | null;
  resolutionStatus: 'MATCHED' | 'AMBIGUOUS' | 'UNMATCHED';
  warnings: string[];
}

export interface ScreenshotDraft {
  importId: string;
  status: 'DRAFT' | 'CONFIRMED' | 'CANCELLED' | 'EXPIRED';
  holdings: ScreenshotCandidate[];
}

export type ImportResult<T> = { data: T; message?: never } | { data: null; message: string };

// An owning integration must explicitly provide this capability. Neither the
// general read client nor demo mode implies permission to replace a portfolio.
export interface PortfolioScreenshotImportClient {
  uploadPortfolioScreenshots(files: File[]): Promise<ImportResult<ScreenshotDraft>>;
  cancelPortfolioImport(importId: string): Promise<ImportResult<ScreenshotDraft>>;
  confirmPortfolioImport(importId: string, rows: ReviewedScreenshotHolding[]): Promise<ImportResult<{
    portfolioSnapshotId: string; holdingsImported: number;
  }>>;
}

const object = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value);
const nullableText = (value: unknown): value is string | null => value === null || typeof value === 'string';
const requiredText = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
// Pydantic Decimal serializes as text. Retain precision: no float conversion.
const decimal = (value: unknown): value is string | null => value === null || typeof value === 'string' && /^-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?$/.test(value);

export function parseScreenshotDraft(value: unknown): ScreenshotDraft | null {
  if (!object(value) || !requiredText(value.import_id)
    || !['DRAFT', 'CONFIRMED', 'CANCELLED', 'EXPIRED'].includes(String(value.status))
    || !Array.isArray(value.holdings)) return null;
  const holdings: ScreenshotCandidate[] = [];
  const ids = new Set<string>();
  for (const row of value.holdings) {
    if (!object(row) || !requiredText(row.row_id) || ids.has(row.row_id)
      || !nullableText(row.instrument_id) || !nullableText(row.symbol) || !nullableText(row.instrument_name)
      || !decimal(row.quantity) || !decimal(row.average_price) || !decimal(row.current_price)
      || !decimal(row.extraction_confidence)
      || !['MATCHED', 'AMBIGUOUS', 'UNMATCHED'].includes(String(row.resolution_status))
      || !Array.isArray(row.field_warnings) || !row.field_warnings.every(requiredText)
      || (row.resolution_status === 'MATCHED' && !requiredText(row.instrument_id))) return null;
    ids.add(row.row_id);
    holdings.push({ rowId: row.row_id, instrumentId: row.instrument_id, symbol: row.symbol,
      instrumentName: row.instrument_name, quantity: row.quantity, averagePrice: row.average_price,
      currentPrice: row.current_price, extractionConfidence: row.extraction_confidence,
      resolutionStatus: row.resolution_status as ScreenshotCandidate['resolutionStatus'], warnings: [...row.field_warnings] });
  }
  return { importId: value.import_id, status: value.status as ScreenshotDraft['status'], holdings };
}

export function screenshotReviewRows(draft: ScreenshotDraft): ReviewedScreenshotHolding[] {
  return draft.holdings.map(({ rowId, instrumentId, symbol, quantity, averagePrice, resolutionStatus }) => ({
    rowId, instrumentId, symbol, quantity, averagePrice, include: resolutionStatus === 'MATCHED',
  }));
}

export function reviewRowsAreComplete(rows: ReviewedScreenshotHolding[]): boolean {
  const included = rows.filter((row) => row.include);
  return included.length > 0 && new Set(rows.map((row) => row.rowId)).size === rows.length
    && included.every((row) => requiredText(row.rowId) && requiredText(row.instrumentId)
      && /^NSE:[A-Za-z0-9._:-]+$/.test(row.instrumentId)
      && positivePlainDecimal(row.quantity) && positivePlainDecimal(row.averagePrice))
    && new Set(included.map((row) => row.instrumentId)).size === included.length;
}

function positivePlainDecimal(value: string | null): boolean {
  return value !== null && /^\d+(?:\.\d+)?$/.test(value) && /[1-9]/.test(value);
}
