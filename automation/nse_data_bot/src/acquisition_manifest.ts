/** Immutable, acquisition-only handoff contract for an official NSE delivery file. */

export const DELIVERY_ACQUISITION_STATUSES = [
  "ACQUIRED",
  "ALREADY_ACQUIRED",
  "NOT_YET_AVAILABLE",
  "SOURCE_UNAVAILABLE",
  "INVALID_RESPONSE",
  "FAILED",
] as const;

export type DeliveryAcquisitionStatus = (typeof DELIVERY_ACQUISITION_STATUSES)[number];

export interface DeliveryAcquisitionManifest {
  readonly family: "DELIVERY";
  readonly requestedSession: string;
  readonly source: "NSE_OFFICIAL";
  readonly sourceFilename: string;
  readonly sourceUrl: string;
  readonly acquiredAt: string;
  readonly byteCount: number;
  readonly sha256: string | null;
  readonly temporaryPath: string | null;
  readonly stagedPath: string | null;
  readonly status: DeliveryAcquisitionStatus;
  readonly errorCode: string | null;
  readonly errorMessage: string | null;
}

export function manifestJson(value: DeliveryAcquisitionManifest): string {
  return JSON.stringify(value);
}
