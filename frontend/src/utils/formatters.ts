/**
 * Formatting utilities for Indian Equities and Institutional Displays.
 * CRITICAL RULE: Missing/null/undefined values must NEVER be formatted as 0 or ₹0.
 */

export function formatINR(val: number | null | undefined, options?: { decimals?: number; showSign?: boolean; fallback?: string }): string {
  if (val === null || val === undefined || isNaN(val)) {
    return options?.fallback ?? '—';
  }

  const decimals = options?.decimals ?? 2;
  const isNegative = val < 0;
  const absVal = Math.abs(val);

  // Format using Indian locale (en-IN)
  const formatted = absVal.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  const sign = isNegative ? '-' : options?.showSign && val > 0 ? '+' : '';
  return `${sign}₹${formatted}`;
}

export function formatCr(val: number | null | undefined, options?: { decimals?: number; fallback?: string }): string {
  if (val === null || val === undefined || isNaN(val)) {
    return options?.fallback ?? '—';
  }
  const decimals = options?.decimals ?? 2;
  const formatted = val.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `₹${formatted} Cr`;
}

export function formatLakh(val: number | null | undefined, options?: { decimals?: number; fallback?: string }): string {
  if (val === null || val === undefined || isNaN(val)) {
    return options?.fallback ?? '—';
  }
  const decimals = options?.decimals ?? 2;
  const formatted = (val / 100000).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `₹${formatted} L`;
}

export function formatPercent(val: number | null | undefined, options?: { decimals?: number; showSign?: boolean; fallback?: string }): string {
  if (val === null || val === undefined || isNaN(val)) {
    return options?.fallback ?? '—';
  }
  const decimals = options?.decimals ?? 2;
  const sign = val > 0 && options?.showSign ? '+' : '';
  return `${sign}${val.toFixed(decimals)}%`;
}

export function formatNumber(val: number | null | undefined, options?: { decimals?: number; showSign?: boolean; fallback?: string }): string {
  if (val === null || val === undefined || isNaN(val)) {
    return options?.fallback ?? '—';
  }
  const decimals = options?.decimals ?? 2;
  const sign = val > 0 && options?.showSign ? '+' : '';
  return `${sign}${val.toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

export function formatScore(val: number | null | undefined, fallback: string = '—'): string {
  if (val === null || val === undefined || isNaN(val)) {
    return fallback;
  }
  return val.toFixed(1);
}

export function formatRatio(val: number | null | undefined, suffix: string = 'x', fallback: string = '—'): string {
  if (val === null || val === undefined || isNaN(val)) {
    return fallback;
  }
  return `${val.toFixed(2)}${suffix}`;
}

export function formatRMultiple(val: number | null | undefined, fallback: string = '—'): string {
  if (val === null || val === undefined || isNaN(val)) {
    return fallback;
  }
  const sign = val > 0 ? '+' : '';
  return `${sign}${val.toFixed(2)}R`;
}
