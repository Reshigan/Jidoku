# ADR-0012 — A system's own metadata is the primary source, not documentation about it

Status: Accepted
Date: 2026-09-01
Supersedes nothing. Relates to ADR-0003 (honest tiers), ADR-0010 (two-tier memory), DP-K01.

## Context

JIDOKA needs to know what an SAP configuration *may* be: which tables exist, which fields they
carry, which values those fields permit, and which objects can be written by machine at all.

The obvious source is SAP's documentation. It is also unusable. SAP's manuals and Notes are
copyrighted and S-user gated; whether we may ingest them at all is DP-K01, which is open and
which invariant 2 says hard-blocks planning that depends on it. A claim sourced to a document we
are not entitled to redistribute also fails on the merits: it cannot be cited to a client's
auditor, and this platform's whole proposition is that every belief carries a reference somebody
can follow.

## Decision

Harvest metadata, not prose.

Everything the platform needs is queryable data inside the system itself:

- an OData `$metadata` document — entity types, keys, property types, lengths, nullability, and
  the value-help or picklist annotation that names a field's check list
- picklist / domain option sets — the *actual permitted values*, as this tenant has them
- the adapter's own `tier_map` — which objects have a write API, which need a human-run file
  load, and which are transported customising with no write path at all

`packages/jidoka-knowledge/harvest.py` reads these through the adapter's existing
`extract(system, entity)` and forms one grounded `Claim` per row, with
`source_ref = harvest:<system_id>:<entity>` and `source_hash` over the row.
`metadata.py` parses EDMX into those rows; it is stdlib ElementTree, matching on local tag names
so the same parser reads both the v2 and v4 documents SAP ships.

## Why this is the better source, not merely the permissible one

A manual states what SAP believed the configuration should be at the release the manual was
written for. Metadata states what *this tenant actually has, now* — and because every claim
carries the hash of the row it was formed from, a second harvest is a comparison rather than an
opinion. That is drift detection, which documentation structurally cannot provide.

## Consequences

**Read-only by construction.** A harvest calls exactly one adapter method: `extract`. No write
path is reachable from this module, which is how invariant 3 holds for a SOURCE_LEGACY or TWIN
system rather than being separately checked. `harvest()` additionally refuses outright if such a
system arrives holding credentials, because that means the registry was bypassed upstream.

**Structure and settings are not interchangeable.** Structure is true of the product and carries
no client value; a setting is one tenant's choice. Only structure is ever offered for promotion
to system memory, and `promotable()` only offers what the scrubber would actually accept, so a
reviewer's queue holds claims a human could approve rather than claims the gate will refuse.

**The harvester proposes; it never promotes.** `scrubber.promote` still requires a named approver
who is not the builder. "This is general SAP truth" is a judgement, and the party proposing it is
exactly the party that must not ratify it (ADR-0010, invariant 7).

**The gate refuses some true facts, and that is correct.** `MaxLength="255"` is general SAP truth
but reads as a literal numeric code; `TKA01` is a real table name indistinguishable from a client
identifier. The scrubber refuses rather than redacts, so these go back to a human to be rewritten
as shapes. Nothing crosses into system memory on a regex's opinion.
`test_a_field_length_keeps_a_structural_fact_out_of_system_memory` pins this.

**DP-K01 stays open and is not needed for this.** Metadata is a fact about a system the client
licenses, and the values in it are the client's own configuration. Neither is SAP's documentation.
What metadata does *not* give is intent — it says `T001` has field `WAERS` with domain `WAERS`,
never why a company code's currency should be set a particular way. That prose corpus remains
DP-K01's question, and remains unbuilt.

## Tests

`packages/jidoka-knowledge/tests/test_harvest.py` — 16 gates, fixture-driven against the mock's
real `$metadata` document. Notably: no write path is ever called; a credentialled SOURCE_LEGACY
system is refused; a changed service definition marks exactly the affected claim STALE and keeps
it; an unregistered system is Unresolvable rather than STALE; two engagements' harvests do not mix.
