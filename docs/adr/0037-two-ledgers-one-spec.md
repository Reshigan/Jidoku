# ADR-0037 — Two implementations of the chain, one spec

Status: Accepted
Date: 2026-09-21
Relates to invariant 4 (the ledger is append-only and hash-chained), ADR-0008 (identity from the
IdP), docs/JIDOKA_DEPLOYMENT_AND_KNOWLEDGE_SPEC.md Part B. Delivers E9's EngagementLedger Durable
Object.

## Context

The platform ships in two shapes and the deployment spec is unambiguous about what that must not
cost: *governance must not vary by hosting*. Phase 2 puts the kernel at the edge, and the first
piece of it is the ledger as a Durable Object — one per engagement, because a DO handles its
requests one at a time and appends therefore cannot race for the same `prev` hash. That is the
property the in-process kernel gets for free and a plain Worker over D1 would not have.

The same spec is equally unambiguous about the danger: *every invariant reimplemented in a second
language is an invariant that can drift out of agreement with the tested one.* And the drift would
not arrive as somebody deciding to weaken a rule. It would arrive because `JSON.stringify` puts no
space after a comma and Python's `json.dumps` does — producing a chain that verifies perfectly
against itself and fails against every chain the kernel ever wrote, discovered the first time an
auditor checks one against the other.

## Decision

**The semantics are a fixture, and both implementations are held to it.**
`packages/jidoka-core/tests/fixtures/ledger_conformance.json` carries the operations, the exact
entries with their exact hashes, the two SoD refusals with their exact messages, and the tamper
point. `test_ledger_conformance.py` holds the kernel to it; `ledger.check.mjs` holds the Durable
Object to it; CI runs both. Two sets of tests that happened to agree would be agreement by
coincidence, and coincidence is what drifts.

**The fixture is generated from the kernel, not written by hand.** The kernel is the definition —
the edge is the port — so the expected hashes are whatever the tested implementation produces.

**The chain is plain JavaScript, not TypeScript.** `chain.mjs` is imported by the Worker and run
unmodified by bare `node`, so the file CI checks is the file that ships. A transpiled copy would
be a third artefact to keep in agreement with the other two. Types live beside it in a `.d.mts`.

**Canonical JSON is written out explicitly** — sorted keys, `ensure_ascii` escaping including
surrogate pairs, `", "` and `": "` separators — with a test asserting each property directly, so
the failure names the cause rather than showing two different hashes.

**Identity comes from the Access header, never the body.** A client that can name its own actor can
name somebody else's, and the ledger's entire value is that the name on an entry is the name of
whoever did it. An unauthenticated append is a 401 with the reason.

**The DO class is deliberately thin.** Storage and addressing only. Every line there is a line that
could hold a rule the kernel does not have.

## Consequences

- The ledger half of "every gate that exists in jidoka-core must exist identically here" is now
  met and checkable. `wrangler.phase2.toml` says so — and says what is still missing before a
  tenant: the registry's write-lock, the executor's arming and snapshot gates, the decision
  engine's STATUTORY and ONE_WAY rules. The ledger being done is not the kernel being done.
- A kernel entry carrying an integral float (`1.0`) would hash differently in the two
  implementations, because JavaScript has one number type. Nothing writes one today; the
  conformance fixture carries a non-integral float to pin the case that does work, and this is the
  known edge rather than a silent one.
- The fixture must be regenerated whenever the entry shape changes, and the Python test fails
  loudly when it is not. That is the intended cost.

## Alternatives rejected

*Two independent test suites.* They would agree until the day they did not, and nothing would
notice, because each would be green against its own idea of the rule.

*Have the Worker call the Python kernel for every append.* That is phase 1, and it is what ships
today. Phase 2 exists because a per-tenant edge ledger is the thing that makes the SaaS shape
possible at all; this is the piece that makes it safe to attempt.

*Store entries in D1 and compute the chain in a stateless Worker.* Two appends racing for the same
`prev` produce two entries claiming the same predecessor, and the chain silently forks. The
Durable Object's single-threaded execution is the reason this design is a DO.
