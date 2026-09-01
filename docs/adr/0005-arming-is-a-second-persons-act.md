# ADR-0005: Arming a live write is a second person's act, separate from executing it
Status: accepted. Invariant 6 says a Tier-A write defaults to dry_run and needs an explicit target plus a
ledger snapshot to go live. This ADR fixes *who*. `ArmedTarget(system_id, armed_by)` cannot be constructed
without naming both, and `Executor` refuses when `armed_by == actor` — the builder may not arm its own write
(invariant 7, restated at the apply path rather than only at approval). Over HTTP the split is structural:
`arm` is an approver-only permission, `execute` a builder-only one, and `auth.py` asserts at import that
neither role holds the other's. Armings are per-target and never inherited: arming S4-DEV does not arm S4-PRD.

Consequences: a live write always has two named humans on the chain before anything is written; armings are
process-local, so a restart disarms rather than leaving a target primed; and an armed step with no bound
connector is a refusal (409), never a no-op reported as success — a fake VERIFIED is the worst outcome
this system could produce.
