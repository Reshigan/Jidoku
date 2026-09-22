# ADR-0039 — A new design supersedes the old one; it does not replace it

Status: Accepted
Date: 2026-09-22
Relates to invariant 1 (unsigned intent is unexecutable), invariant 2 (open decisions hard-block),
ADR-0019 (drift is a blocking decision), ADR-0021 (assurance), ADR-0010 (memory supersedes,
never overwrites).

## Context

`POST /ir` did `e.ir, e.open_dps = loaded, open_dps`. A wholesale replace, one ledger line reading
"47 records", and nothing else. On a real programme the workbook goes v1 → v2 → v3 every few
weeks, so this was the normal path rather than an edge case, and it lost two different things.

The first is the design history. Which records were new, which were gone, which had been edited
under the same key — none of it was recorded, and a history that cannot be read back is not one.

The second is worse and is a correctness hole. Verification iterates the *current* IR set, and so
does assurance. A record that was executed against a customer's system and then dropped from v2
disappeared from every projection the platform has — while the change sat in their tenant, with
its ledger entries intact and nothing reading them. For a platform whose promise is signed intent
in and verified configuration out, a live change it can no longer see is the worst thing it can
produce. `jidoka-knowledge` has done this correctly for beliefs since ADR-0010 — supersede, never
overwrite, the prior claim survives — and signed intent had no equivalent.

## Decision

**The diff is computed before the old set is gone** and written to the chain as `SUPERSEDED`,
carrying the added, removed and changed keys. Only where there was a previous set: a first load
adds every record and supersedes nothing, and an entry saying otherwise would make the word mean
less every time it appeared.

**A record the new design drops, that a customer's system is still holding, is an orphan.**
Determined from the chain rather than from the old IR — what matters is not that the record
existed, it is that something was done to a live system on its account. `EXECUTED`, `VERIFIED`,
`DRIFT_DETECTED`, `PARTIAL`, `ATTESTED` and `HANDED_OFF` count; a later `ROLLED_BACK` clears it,
because the platform has already cleaned up after itself and chasing it would be nagging about its
own work.

**An orphan gets drift's treatment, because it is drift's sibling.** A `DESIGN` decision point with
exactly two exits — sign it back into the design, or take it out of the system — which hard-blocks
planning through invariant 2's existing gate. JIDOKA does not pick; it refuses to plan around a
change nobody claims.

**The night shift chases it** at cost 85, between a half-landed write and a failing control, so
nobody has to open the console to discover it.

**The console keeps the load dialog open** when a load strands something, and says what. A clean
load closes and reports what it superseded; a load that left something live and unclaimed is not a
clean load.

## Consequences

- A workbook that removes a record which was only ever planned, never built, is dropped without
  ceremony. A design that changed its mind before anything reached a tenant owes nobody an
  explanation.
- Planning halts on an orphan. That is strong, and it is the same strength drift already has: the
  alternative is planning new work around a live change the design does not describe.
- `changed` compares the `intent` tree only. A record whose tier, binding or contract moved under
  the same key is reported as unchanged, which understates the diff. The key case — the configured
  values moved — is covered, and this is the known edge rather than a silent one.
- Nothing here removes the orphaned record's ledger history, and nothing should: the chain is the
  record that the change was made, and it is the only reason the platform can see the orphan at
  all.

## Alternatives rejected

*Refuse the load while a record is live.* It would make every design revision a two-step dance and
push people to edit workbooks around the platform. The load succeeds; the plan is what halts.

*Auto-roll-back what the design dropped.* A write to a customer's system on the strength of
somebody deleting a row in a spreadsheet. Invariant 6 exists to stop exactly that.

*Keep dropped records in the IR set, flagged.* Then `e.ir` no longer means "the signed design",
and every projection over it would need to learn the exception. The chain already holds the fact;
the decision point already holds the question.
