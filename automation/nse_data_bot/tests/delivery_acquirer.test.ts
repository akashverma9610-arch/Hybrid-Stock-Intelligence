import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync } from "node:fs";
import { mkdtemp, mkdir, readFile, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import { acquireDelivery, officialDeliveryFilename, officialDeliveryUrl } from "../src/delivery_acquirer.ts";

const body = "SYMBOL,SERIES,DATE1,TTL_TRD_QNTY,DELIV_QTY,DELIV_PER\nALPHA,EQ,29-Aug-2026,100,61,61\n";

async function root(): Promise<string> {
  const value = await mkdtemp(path.join(os.tmpdir(), "hsi-delivery-acquirer-"));
  await Promise.all([mkdir(path.join(value, "app")), mkdir(path.join(value, "data")), mkdir(path.join(value, "automation"))]);
  await writeFile(path.join(value, "pyproject.toml"), "[project]\nname='test'\n");
  return value;
}

function response(value = body, status = 200): typeof fetch {
  return async () => new Response(value, { status });
}

test("constructs the exact official filename and URL", () => {
  assert.equal(officialDeliveryFilename("2026-08-29"), "sec_bhavdata_full_29082026.csv");
  assert.equal(officialDeliveryUrl("2026-08-29"), "https://archives.nseindia.com/products/content/sec_bhavdata_full_29082026.csv");
});

test("writes original bytes to a temporary partial file then atomically stages them", async () => {
  const hsiRoot = await root();
  const manifest = await acquireDelivery({ requestedSession: "2026-08-29", root: hsiRoot, fetchImpl: response(), minimumPacingMs: 0 });
  const expected = path.join(hsiRoot, "data", "incoming", "delivery", "sec_bhavdata_full_29082026.csv");
  assert.equal(manifest.status, "ACQUIRED");
  assert.equal(manifest.stagedPath, expected);
  assert.equal(manifest.byteCount, Buffer.byteLength(body));
  assert.equal(manifest.sha256, createHash("sha256").update(body).digest("hex"));
  assert.equal(await readFile(expected, "utf8"), body);
  assert.equal(existsSync(manifest.temporaryPath!), false);
  assert.equal(existsSync(path.join(hsiRoot, "data", "canonical_hsi.db")), false);
});

test("same official bytes are not staged twice", async () => {
  const hsiRoot = await root();
  const first = await acquireDelivery({ requestedSession: "2026-08-29", root: hsiRoot, fetchImpl: response(), minimumPacingMs: 0 });
  const second = await acquireDelivery({ requestedSession: "2026-08-29", root: hsiRoot, fetchImpl: response(), minimumPacingMs: 0 });
  assert.equal(first.status, "ACQUIRED");
  assert.equal(second.status, "ALREADY_ACQUIRED");
  assert.equal(second.stagedPath, null);
});

test("failed source request does not stage a partial or synthetic file", async () => {
  const hsiRoot = await root();
  const manifest = await acquireDelivery({ requestedSession: "2026-08-29", root: hsiRoot, fetchImpl: response("", 404), minimumPacingMs: 0 });
  const incoming = path.join(hsiRoot, "data", "incoming", "delivery", "sec_bhavdata_full_29082026.csv");
  const tmp = path.join(hsiRoot, "automation", "nse_data_bot", "tmp");
  assert.equal(manifest.status, "NOT_YET_AVAILABLE");
  assert.equal(existsSync(incoming), false);
  assert.equal(existsSync(tmp) ? (await (await import("node:fs/promises")).readdir(tmp)).some((name) => name.endsWith(".partial")) : false, false);
});

test("network failure is safely classified without staging bytes", async () => {
  const hsiRoot = await root();
  const fetchFailure: typeof fetch = async () => { throw new TypeError("network unavailable"); };
  const manifest = await acquireDelivery({ requestedSession: "2026-08-29", root: hsiRoot, fetchImpl: fetchFailure, minimumPacingMs: 0 });
  assert.equal(manifest.status, "SOURCE_UNAVAILABLE");
  assert.equal(manifest.errorCode, "NSE_DELIVERY_SOURCE_UNAVAILABLE");
  assert.equal(existsSync(path.join(hsiRoot, "data", "incoming", "delivery", "sec_bhavdata_full_29082026.csv")), false);
});

test("root containment rejects a non-HSI root", async () => {
  const invalid = await mkdtemp(path.join(os.tmpdir(), "not-hsi-"));
  const manifest = await acquireDelivery({ requestedSession: "2026-08-29", root: invalid, fetchImpl: response(), minimumPacingMs: 0 });
  assert.equal(manifest.status, "FAILED");
  assert.equal(manifest.errorCode, "HSI_ROOT_INVALID");
});
