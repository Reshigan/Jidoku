# ADR-0043 — The verifier ships, and it is allowed to disagree

Status: Accepted
Date: 2026-09-23
Relates to invariant 4 (the ledger is append-only and hash-chained), ADR-0021 (assurance),
ADR-0031 (the platform keeps its own record), ADR-0037 (two implementations of the chain, one
spec).

## Context

`GET /ledger/evidence` has described itself as *"auditor-verifiable… offline-checkable"* since E2.
The bundle carries the chain, the genesis constant, the hashing rule written out in prose, and a
manifest digest. All of that is true, and for a year nothing shipped that actually checked it.

So an auditor had two options: believe the `verification: {"verified": true}` block inside the
bundle, or write the verifier themselves from the prose. The first is not verification — a
platform that got the chain wrong, or lied about it, prints the same word. The second is a real
ask of someone who bills by the hour, and until they do it the strongest claim this product makes
rests on trusting the product.

That is precisely the shape of thing this codebase refuses everywhere else: a claim with no
mechanism behind it.

## Decision

**`tools/jidoka-verify.py` ships, and it is standard library only.** No third-party import, no
network, no install step, one file an auditor can read in a sitting and run on a laptop.

**It imports nothing from JIDOKA.** The chain rule and the assurance formula are restated inside
it. That is a deliberate third copy — the Python kernel, the Durable Object, and this — because a
verifier that imported the platform's implementation would be the platform checking its own work,
which is the one thing it exists not to be. Like the Durable Object, it is held to
`ledger_conformance.json`, so the three agree by test rather than by coincidence (ADR-0037).

**It recomputes, then contradicts.** Every figure is derived from the entries and compared against
what the bundle claims: the manifest digest, the chain, the `verified` flag, the assurance
numerator and denominator, and every `separation_held` and `snapshot_present` boolean. Where they
differ it says so, naming both sides — *"the producer and an independent check disagree"*. That
is the one check a vendor cannot perform on its own behalf.

**The bundle now carries the assurance figure.** It could not be contradicted while it existed
only on a screen. A bundle that carried the evidence and not the claim would leave the number to
be quoted from somewhere nobody can check.

**A clean result says what it does not mean.** *"This says the record is internally consistent and
unaltered. It does not say the record is complete: a change made outside the platform leaves
nothing here to check."* A verifier that printed "verified" and stopped would be read as a
statement about the customer's system, and it is a statement about a file.

**The tests run it as a subprocess**, against bundles the real API produced. Importing it into the
test suite would let it quietly acquire the platform's code through the test's own environment.

## Consequences

- The strongest claim in `CLAIMS.md` — a chain an auditor can verify offline — is now
  demonstrable rather than argued. It can be handed to a Big Four team who can confirm it on their
  own machines without the vendor present.
- Three implementations of one rule now exist. Each added one is a liability; the conformance
  fixture is what makes it a manageable one, and a fourth would need the same treatment or a very
  good reason.
- The verifier reports a self-approval even where the bundle's own table calls it separated,
  because it recomputes from the entries. A producer cannot make a bad approval look good by
  writing `true` in the summary.
- It cannot see what never reached the platform. That limit is printed on every successful run
  rather than left in the documentation, and closing it is the reconciliation work that follows
  this.

## Alternatives rejected

*Publish the procedure and let auditors implement it.* That is what shipped for a year, and the
result was that nobody did. A procedure in prose is a claim; a script that exits 1 is a check.

*Have the verifier call the API to fetch the bundle.* Then it needs credentials, a network path
and a reachable platform, and it stops being the thing that works when the vendor is gone — which
is the situation an evidence export is for.

*Import `jidoka_core.ledger` to avoid a third copy.* It would make the tool smaller and useless:
an auditor checking the platform with the platform's own code has verified nothing.
