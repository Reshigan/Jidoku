# ADR-0010: Memory is two-tier, evidence-grounded, and correctable

Status: accepted.

An agent that remembers text drifts the moment the system it described changes. An agent that
remembers nothing re-derives the same engagement from scratch every session. Neither is a
consultant. JIDOKA stores *claims*, and every claim carries the evidence it was formed from and
the exact version of that evidence.

## Two tiers

**Project memory** is scoped to one `engagement_id` — the same boundary the ledger, IR, and
decision register already use. It holds what is true of this client: their org shape, their
naming conventions, their decided values, what was observed in their systems. It never leaves
the engagement. Purge remains a delete, not a query.

**System memory** is cross-project and holds three things only: principles (near-immutable;
changing one is itself a decision point), the promotion-gated skill library, and — if DP-K01
ever resolves — the K2 SAP corpus. It is what JIDOKA knows about SAP, never about a client.

The asymmetry is the design. Project memory reads system memory freely. System memory learns
from a project only through the scrubber gate: shapes may cross, values never. "Cost centre
codes here were four-digit numeric" is a shape. `1000` is a value. Promotion is a ledgered
ceremony with a named human approver, in the same class as arming a live write, because a
client value leaked into the shared library is unrecallable.

## Evidence grounding

A claim without a source is not storable. Every claim records `source_ref` (the IR record,
ledger entry, or live SAP object it came from) and `source_hash` (that evidence as it read at
the time). This is what makes staleness deterministic.

## Staleness is a hash comparison, not a model call

A claim is stale when its evidence moved. For IR- and ledger-grounded claims that is a hash
comparison. For claims grounded in a live system it is the adapter's existing
`verify(ir_record, live_state)` returning `DRIFT` or `MISSING`. No inference, no cost, no
model in the loop — so it can run on every read.

## Durable uncertainty

A stale claim is flagged, never deleted and never silently refreshed. It keeps its badge until
something re-verifies it against the source. An agent reading a stale claim must either
re-verify it or say it is unverified; it may not present it as fact. This is the same
principle as the existing rule that conflicts are surfaced as findings rather than silently
resolved: uncertainty that disappears quietly is indistinguishable from confidence.

Supersession, not overwrite. A corrected claim closes the prior claim's validity interval and
records what it superseded. Memory that only appends is sediment; memory that overwrites has
no audit trail. Validity intervals give both.

## Concurrency

One OS process per engagement, each with its own budget and write-lock, dispatched through the
existing capability-checked syscall table. There is no syscall that reads another engagement's
memory — cross-project reach is absent from the API rather than blocked by a check. Two
projects running at once cannot cross because there is no instruction that would let them.

## Consequences

Every memory write is a ledger entry, so belief has the same audit surface as configuration.
Claims cost more to store than text. Promotion to system memory requires a human, which makes
shared learning slow — deliberately, because it is the only flow that crosses a tenant
boundary.
