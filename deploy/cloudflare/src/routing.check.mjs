// Self-check for the Worker's one branch: kernel or console. `node src/routing.check.mjs`.
// Wrong answers here are silent — an API call returns index.html with a 200 — so it gets a check.
// Duplicated rather than imported because the Worker is TS and this must run with bare node.
const API_PREFIXES = ["/engagements", "/health", "/auth", "/schema", "/openapi.json"];
const isApi = (p) => API_PREFIXES.some((x) => p === x || p.startsWith(x + "/"));

import { readFileSync } from "node:fs";
import assert from "node:assert/strict";

// The list here must stay the list there.
const src = readFileSync(new URL("./index.ts", import.meta.url), "utf8");
assert.match(src, new RegExp(`API_PREFIXES = ${JSON.stringify(API_PREFIXES).replace(/[[\]]/g, "\\$&").replace(/,/g, ", ")}`),
  "API_PREFIXES drifted from this check");

for (const p of ["/engagements", "/engagements/e1/ledger", "/health", "/auth/token", "/openapi.json"])
  assert.equal(isApi(p), true, `${p} must reach the kernel`);
for (const p of ["/", "/ledger", "/assets/app.js", "/healthz", "/schemas", "/authors"])
  assert.equal(isApi(p), false, `${p} must be served as the console`);

// --- the night shift's clock ------------------------------------------------------------------
// The scheduled handler calls the kernel rather than reimplementing the shift, so what this can
// check is the part that is easy to get silently wrong: which paths it calls, and that it refuses
// to call anything at all when it has no token.
const nightTargets = (engagements) => engagements.map((e) => `/engagements/${e.engagement_id}/nightshift`);

assert.deepEqual(nightTargets([{ engagement_id: "e1" }, { engagement_id: "e2" }]),
  ["/engagements/e1/nightshift", "/engagements/e2/nightshift"],
  "the night must post to each engagement's own nightshift");
for (const p of nightTargets([{ engagement_id: "e1" }]))
  assert.equal(isApi(p), true, `${p} must reach the kernel, not the console`);

assert.match(src, /export const nightTargets/, "nightTargets drifted from this check");
assert.match(src, /NIGHT_TOKEN/, "the scheduled run must carry a token");
assert.match(src, /no night was worked/,
  "an unconfigured night must say so: a silent no-op is a shift nobody knows stopped happening");
assert.match(readFileSync(new URL("../wrangler.toml", import.meta.url), "utf8"), /crons\s*=/,
  "the worker has a scheduled handler and no cron to fire it");

console.log("routing ok");
console.log("night shift clock ok");
