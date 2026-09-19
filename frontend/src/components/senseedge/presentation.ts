import type { MarketWideWatchRecordData, PortfolioRuntimeHolding } from '../../types/devConsole';

export const human = (value: string | null | undefined): string => value ? value.replace(/_/g, ' ') : 'Unavailable';
export const display = (value: string | number | null | undefined): string => value === null || value === undefined ? '—' : String(value);
export function filterWatch(rows: MarketWideWatchRecordData[], search: string, archetype: string) {
  const query = search.trim().toLowerCase();
  return rows.filter((row) => (archetype === 'ALL' || row.archetypes.includes(archetype))
    && `${row.symbol} ${row.companyName ?? ''} ${row.canonicalInstrumentId}`.toLowerCase().includes(query));
}
export function sectorCounts(rows: PortfolioRuntimeHolding[]): Array<[string, number]> {
  const counts = new Map<string, number>();
  rows.forEach((row) => counts.set(row.sector || 'Unclassified', (counts.get(row.sector || 'Unclassified') ?? 0) + 1));
  return [...counts.entries()].sort(([a, ac], [b, bc]) => bc - ac || a.localeCompare(b, 'en'));
}
export function cashLabel(status: string | null | undefined, amount: string | number | null | undefined): string {
  return status === 'KNOWN' && amount !== null && amount !== undefined ? String(amount) : 'UNKNOWN';
}
// CSV is a user-triggered export of the currently displayed view, not a report
// publication. Neutralize spreadsheet formula prefixes from source text.
export function csvCell(value: unknown): string {
  let text = value === null || value === undefined ? '' : String(value);
  if (/^[\s]*[=+@-]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}
