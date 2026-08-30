/**
 * Acquisition-only official NSE delivery handoff.
 *
 * This module never parses market data, writes a database, schedules work, or
 * falls back to fixtures.  HSI/U17 remains the sole validator and ingestor.
 */

import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, rename, rm, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  type DeliveryAcquisitionManifest,
  type DeliveryAcquisitionStatus,
  manifestJson,
} from "./acquisition_manifest.ts";

const SOURCE = "https://archives.nseindia.com/products/content";
const DEFAULT_TIMEOUT_MS = 15_000;
const DEFAULT_MINIMUM_PACING_MS = 750;
let lastRequestAt = 0;

export interface DeliveryAcquisitionOptions {
  readonly requestedSession: string;
  readonly root?: string;
  readonly timeoutMs?: number;
  readonly minimumPacingMs?: number;
  readonly fetchImpl?: typeof fetch;
  readonly now?: () => Date;
}

export function officialDeliveryFilename(requestedSession: string): string {
  const [year, month, day] = strictSession(requestedSession);
  return `sec_bhavdata_full_${day}${month}${year}.csv`;
}

export function officialDeliveryUrl(requestedSession: string): string {
  return `${SOURCE}/${officialDeliveryFilename(requestedSession)}`;
}

export function resolveHsiRoot(explicitRoot?: string): string {
  const requested = explicitRoot || process.env.HSI_ROOT;
  if (requested) {
    const candidate = path.resolve(requested);
    if (isHsiRoot(candidate)) return candidate;
    throw new Error("HSI_ROOT_INVALID");
  }
  let candidate = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
  while (candidate !== path.dirname(candidate)) {
    if (isHsiRoot(candidate)) return candidate;
    candidate = path.dirname(candidate);
  }
  throw new Error("HSI_ROOT_NOT_FOUND");
}

export async function acquireDelivery(options: DeliveryAcquisitionOptions): Promise<DeliveryAcquisitionManifest> {
  const requestedSession = canonicalSession(options.requestedSession);
  const sourceFilename = officialDeliveryFilename(requestedSession);
  const sourceUrl = officialDeliveryUrl(requestedSession);
  const now = options.now || (() => new Date());
  const acquiredAt = now().toISOString();
  const base = manifestBase(requestedSession, sourceFilename, sourceUrl, acquiredAt);
  let temporaryPath: string | null = null;

  try {
    const root = resolveHsiRoot(options.root);
    const temporaryRoot = child(root, "automation", "nse_data_bot", "tmp");
    const incomingRoot = child(root, "data", "incoming", "delivery");
    const archiveRoot = child(root, "data", "archive", "delivery");
    const quarantineRoot = child(root, "data", "quarantine", "delivery");
    await Promise.all([mkdir(temporaryRoot, { recursive: true }), mkdir(incomingRoot, { recursive: true })]);

    await pace(options.minimumPacingMs ?? DEFAULT_MINIMUM_PACING_MS);
    const response = await fetchOfficial(sourceUrl, options.fetchImpl || fetch, options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
    if (!response.ok) return httpFailure(base, response.status);
    const bytes = Buffer.from(await response.arrayBuffer());
    if (bytes.length === 0) return failure(base, "INVALID_RESPONSE", "NSE_DELIVERY_RESPONSE_EMPTY");

    const sha256 = createHash("sha256").update(bytes).digest("hex");
    temporaryPath = child(temporaryRoot, `${sourceFilename}.${randomUUID()}.partial`);
    await writeFile(temporaryPath, bytes, { flag: "wx" });

    const stagedPath = child(incomingRoot, sourceFilename);
    const existing = await duplicateState(stagedPath, archiveRoot, quarantineRoot, sourceFilename, sha256);
    if (existing === "MATCH") {
      await removeQuietly(temporaryPath);
      return { ...base, byteCount: bytes.length, sha256, temporaryPath, stagedPath: null, status: "ALREADY_ACQUIRED", errorCode: null, errorMessage: null };
    }
    if (existing === "QUARANTINED") {
      await removeQuietly(temporaryPath);
      return failure(base, "FAILED", "KNOWN_QUARANTINED_ARTIFACT", bytes.length, sha256, temporaryPath);
    }
    if (existing === "COLLISION") {
      await removeQuietly(temporaryPath);
      return failure(base, "FAILED", "STAGING_FILENAME_CONFLICT", bytes.length, sha256, temporaryPath);
    }

    await rename(temporaryPath, stagedPath);
    return { ...base, byteCount: bytes.length, sha256, temporaryPath, stagedPath, status: "ACQUIRED", errorCode: null, errorMessage: null };
  } catch (error) {
    await removeQuietly(temporaryPath);
    const code = error instanceof Error ? error.message : "NSE_DELIVERY_ACQUISITION_FAILED";
    if (code === "NSE_DELIVERY_SOURCE_UNAVAILABLE") {
      return failure(base, "SOURCE_UNAVAILABLE", code, 0, null, temporaryPath);
    }
    return failure(base, "FAILED", code.startsWith("HSI_ROOT_") ? code : "NSE_DELIVERY_ACQUISITION_FAILED", 0, null, temporaryPath);
  }
}

function canonicalSession(value: string): string {
  const [year, month, day] = strictSession(value);
  return `${year}-${month}-${day}`;
}

function strictSession(value: string): [string, string, string] {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) throw new Error("REQUESTED_SESSION_INVALID");
  const [, year, month, day] = match;
  const parsed = new Date(`${year}-${month}-${day}T00:00:00.000Z`);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value) throw new Error("REQUESTED_SESSION_INVALID");
  return [year, month, day];
}

function isHsiRoot(candidate: string): boolean {
  return ["app", "data", "automation", "pyproject.toml"].every((entry) => existsSync(path.join(candidate, entry)));
}

function child(root: string, ...parts: string[]): string {
  const target = path.resolve(root, ...parts);
  const relative = path.relative(root, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) throw new Error("HSI_PATH_ESCAPE");
  return target;
}

async function fetchOfficial(url: string, fetchImpl: typeof fetch, timeoutMs: number): Promise<Response> {
  const signal = AbortSignal.timeout(timeoutMs);
  try {
    return await fetchImpl(url, {
      headers: {
        "Accept": "text/csv,application/csv,text/plain;q=0.9,*/*;q=0.1",
        "Referer": "https://www.nseindia.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
      },
      signal,
    });
  } catch {
    throw new Error("NSE_DELIVERY_SOURCE_UNAVAILABLE");
  }
}

async function pace(minimumPacingMs: number): Promise<void> {
  const wait = Math.max(0, minimumPacingMs - (Date.now() - lastRequestAt));
  if (wait) await new Promise<void>((resolve) => setTimeout(resolve, wait));
  lastRequestAt = Date.now();
}

async function duplicateState(stagedPath: string, archiveRoot: string, quarantineRoot: string, sourceFilename: string, sha256: string): Promise<"NONE" | "MATCH" | "COLLISION" | "QUARANTINED"> {
  if (existsSync(stagedPath)) return (await checksumMatches(stagedPath, sha256)) ? "MATCH" : "COLLISION";
  const parsed = path.parse(sourceFilename);
  const archived = path.join(archiveRoot, `${parsed.name}-${sha256.slice(0, 12)}${parsed.ext.toLowerCase()}`);
  if (existsSync(archived) && await checksumMatches(archived, sha256)) return "MATCH";
  const quarantined = path.join(quarantineRoot, `${parsed.name}-${sha256.slice(0, 12)}${parsed.ext.toLowerCase()}`);
  if (existsSync(quarantined) && await checksumMatches(quarantined, sha256)) return "QUARANTINED";
  return "NONE";
}

async function checksumMatches(filePath: string, expected: string): Promise<boolean> {
  const bytes = await readFile(filePath);
  return createHash("sha256").update(bytes).digest("hex") === expected;
}

function manifestBase(requestedSession: string, sourceFilename: string, sourceUrl: string, acquiredAt: string): Omit<DeliveryAcquisitionManifest, "byteCount" | "sha256" | "temporaryPath" | "stagedPath" | "status" | "errorCode" | "errorMessage"> {
  return { family: "DELIVERY", requestedSession, source: "NSE_OFFICIAL", sourceFilename, sourceUrl, acquiredAt };
}

function failure(base: ReturnType<typeof manifestBase>, status: DeliveryAcquisitionStatus, errorCode: string, byteCount = 0, sha256: string | null = null, temporaryPath: string | null = null): DeliveryAcquisitionManifest {
  return { ...base, byteCount, sha256, temporaryPath, stagedPath: null, status, errorCode, errorMessage: errorCode };
}

function httpFailure(base: ReturnType<typeof manifestBase>, statusCode: number): DeliveryAcquisitionManifest {
  if (statusCode === 404) return failure(base, "NOT_YET_AVAILABLE", "NSE_DELIVERY_NOT_YET_AVAILABLE");
  if (statusCode === 401 || statusCode === 403 || statusCode === 408 || statusCode === 429 || statusCode >= 500) return failure(base, "SOURCE_UNAVAILABLE", `NSE_DELIVERY_HTTP_${statusCode}`);
  return failure(base, "INVALID_RESPONSE", `NSE_DELIVERY_HTTP_${statusCode}`);
}

async function removeQuietly(filePath: string | null): Promise<void> {
  if (filePath) await rm(filePath, { force: true }).catch(() => undefined);
}

function cliArguments(args: string[]): { requestedSession: string; root?: string; timeoutMs?: number } {
  if (args[0] !== "acquire-delivery") throw new Error("DELIVERY_ACQUIRER_COMMAND_INVALID");
  const value = (flag: string): string | undefined => {
    const index = args.indexOf(flag);
    return index >= 0 ? args[index + 1] : undefined;
  };
  const requestedSession = value("--date");
  if (!requestedSession) throw new Error("REQUESTED_SESSION_REQUIRED");
  const rawTimeout = value("--timeout-ms");
  const timeoutMs = rawTimeout === undefined ? undefined : Number(rawTimeout);
  if (timeoutMs !== undefined && (!Number.isInteger(timeoutMs) || timeoutMs < 1)) throw new Error("DELIVERY_ACQUIRER_TIMEOUT_INVALID");
  return { requestedSession, root: value("--root"), timeoutMs };
}

if (process.argv[1] && import.meta.url === new URL(`file://${process.argv[1].replaceAll("\\", "/")}`).href) {
  try {
    const manifest = await acquireDelivery(cliArguments(process.argv.slice(2)));
    process.stdout.write(`${manifestJson(manifest)}\n`);
  } catch (error) {
    const code = error instanceof Error ? error.message : "NSE_DELIVERY_ACQUISITION_FAILED";
    process.stdout.write(`${manifestJson(failure(manifestBase("", "", "", new Date().toISOString()), "FAILED", code))}\n`);
  }
}
