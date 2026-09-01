# ADR-0014 — Number ranges are ledgered allocations

Status: Accepted
Date: 2026-09-01
Relates to ADR-0002 (hash-chained ledger), invariant 2.

## Context

SAP projects burn weeks on numbering collisions: two consultants take CC-ZA-0100, a wave-2 team
reuses codes wave 1 retired, a spreadsheet of "reserved" ranges goes stale the day it is mailed.
The range registry is traditionally a document — and documents drift.

## Decision

`jidoka_core.numbering.NumberRanges` governs codes per object type. Ranges are registered once
(overlaps refused), allocations append `CODE_ALLOCATED` to the engagement ledger, and a collision
is refused **naming the holder**. Codes are never released: a retired object's code stays burned,
because reuse is how historical reporting breaks. There is no deallocate method, and a test
asserts its absence.

The ledger is the storage. Registrations ride in `RANGE_REGISTERED` entries (the range definition
in extras) and the registry rebuilds by replay on rehydration — no new table, and the numbering
history is inside the same hash chain as everything else.

IR upload enforces it: a record whose external code violates a governed range is refused at load
(422) before anything is kept. Object types with no registered range stay unconstrained.
