# ADR-0042 — Two environments, compared, with neither one the baseline

Status: Accepted
Date: 2026-09-23
Relates to invariant 3 (SOURCE_LEGACY and TWIN hold no write credentials), ADR-0003 (tiers),
ADR-0012 (harvesting through a read-only binding), ADR-0019 (drift).

## Context

The registry has modelled `DEV`, `TEST` and `PROD` since the first commit. `build_reader` has
given a binding that reads a system and structurally cannot write to it since ADR-0012. Every
adapter has carried a `diff`. Nothing put the three together, so the question a consultant answers
by hand before every cutover — *is QA the same as PROD, and what is in DEV that never made it
across?* — was one the platform held every piece of and never asked.

It is also an assurance gap. An IR record binds to one `system_binding`, so a record verified in
DEV says nothing about PROD, and the evidence statement has no way to express "proven, and proven
*where*".

## Decision

**Neither side is "before".** The adapters' `diff` is deliberately directional — it answers "what
did my write do", where one side precedes the other. Reusing it here would make one environment
the baseline and the other a list of additions and deletions from it, which reads as a verdict
nobody gave. The comparison says *only in this one*, *only in that one*, *both, differing*, and
leaves which is right to whoever knows why.

**Signed intent is the third party.** Where the design describes the object, the report says which
side matches it — *"matches signed intent in KOM-SF-QA and does not in KOM-SF-PROD"* — which is a
far more useful sentence than "these two rows are not equal". Where it does not, the difference is
still reported, and it says so: an undesigned object present in PROD and absent in DEV is exactly
the thing somebody wants to find before a cutover.

**It reads, and it needs only `read`.** The refusal for an unbound system points at
`POST /execution/connector/reader` specifically, because the system being compared is usually one
no IR record binds to — the design names DEV and the question is about PROD — and the reader takes
its product from the registry rather than from intent. A comparison that could write would be an
execute wearing a lab coat.

**Only what the engagement designed.** The entities its signed intent touches, not the adapter's
whole tier map. A diff of every object a product publishes is a report nobody reads.

**What could not be read is listed, never dropped.** A comparison that quietly skipped an
unreadable entity would report alignment it never checked.

**Tenant-generated metadata is excluded** — `lastModifiedDateTime`, `createdBy` and their
relatives. Comparing them would report every object as differing on fields the tenant writes
itself.

## Consequences

- Two systems of different products are refused rather than diffed. A diff across products would
  report every object as missing from one side, which is true and useless.
- Nested values are not compared. Only scalar fields are, so a difference buried in a nested
  structure is reported as "the same". That is the known edge, and widening it means deciding what
  a meaningful difference inside a nested object is — a per-product question this does not
  pretend to answer.
- The comparison reads both systems on every call, which is the cost of not caching a fact about
  somebody else's tenant. A cached answer about PROD is a claim about a system the platform has
  not looked at.
- It does not raise a decision point. Drift is a difference between signed intent and one system
  the engagement owns; this is a difference between two systems, which may be entirely correct —
  DEV is supposed to be ahead. Making it blocking would stop work for a difference that is often
  the plan.

## Alternatives rejected

*Reuse the adapter `diff`.* Discussed above: it has a direction, and here there is none.

*Compare everything in the tier map.* A programme configures a fraction of what a product
publishes, and the rest is delivered standard that differs between tenants for reasons nobody on
the engagement caused.

*Treat a difference as drift.* Drift has an owner — the person who signed the record — and two
exits. A difference between environments has neither until somebody says which side is meant to
be right, and the platform does not know.
