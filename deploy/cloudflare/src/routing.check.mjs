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

console.log("routing ok");
