// The Durable Object's chain, held to the kernel's own conformance fixture.
//
// `node src/ledger.check.mjs`. It runs the same operations the Python suite runs
// (packages/jidoka-core/tests/test_ledger_conformance.py) against the same file, and asserts the
// same hashes, the same refusal messages and the same tamper point. Two implementations of one
// chain is the one place "governance must not vary by hosting" can quietly stop being true, so it
// is the one place with a shared spec rather than two sets of tests that agree by coincidence.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";

if (!globalThis.crypto) globalThis.crypto = webcrypto;   // Workers has it; bare node may not.

import { Chain, GENESIS, SoDViolation, canonical } from "./chain.mjs";

const spec = JSON.parse(readFileSync(
  new URL("../../../packages/jidoka-core/tests/fixtures/ledger_conformance.json", import.meta.url),
  "utf8"));

// --- the canonical form, which is the whole reason this file exists ---------------------------
assert.equal(canonical({ b: 1, a: "x" }), '{"a": "x", "b": 1}',
  "keys sort and the separators carry spaces — JSON.stringify does neither");
assert.equal(canonical({ "café": "naïve" }), '{"caf\\u00e9": "na\\u00efve"}',
  "non-ASCII is escaped, like Python's ensure_ascii");
assert.equal(GENESIS, spec.genesis, "genesis drifted from the spec");

// --- replay ------------------------------------------------------------------------------------
async function replay() {
  const chain = new Chain();
  const stamps = spec.expected.map((e) => e.ts);
  let i = 0;
  for (const op of spec.operations) {
    if (op.op === "append") {
      await chain.append(op.task, op.action, op.actor, op.detail, op.extra, stamps[i]);
    } else {
      await chain.approve(op.task, op.reviewer, stamps[i]);
    }
    i += 1;
  }
  return chain;
}

const chain = await replay();
assert.deepEqual(chain.entries, spec.expected,
  "the Durable Object's chain does not match the kernel's, byte for byte");

// --- the refusals, word for word ---------------------------------------------------------------
for (const sod of spec.sod) {
  await assert.rejects(() => chain.approve(sod.task, sod.reviewer),
    (err) => {
      assert.ok(err instanceof SoDViolation, sod.why);
      assert.equal(err.message, sod.message,
        "an operator must read one message wherever the platform is hosted");
      return true;
    });
}

// --- tamper-evidence ----------------------------------------------------------------------------
const tampered = await replay();
tampered.entries[spec.tamper.index][spec.tamper.field] = spec.tamper.to;
await assert.rejects(() => tampered.verify(), /Chain broken/, spec.tamper.why);
assert.equal(await (await replay()).verify(), true);

console.log(`ledger conformance ok — ${spec.expected.length} entries, ${spec.sod.length} refusals`);
