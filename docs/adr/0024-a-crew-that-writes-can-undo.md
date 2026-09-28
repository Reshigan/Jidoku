# ADR-0024 — A crew that writes can undo

Status: Accepted
Date: 2026-09-21
Relates to ADR-0009 (rollback is a write path), ADR-0020 (the crew spends an arming),
invariants 3, 4, 6 and 7.

## Context

ADR-0020 gave the operator `sys_write_tier_a` and `sys_advance_transport`. It did not give it
`sys_rollback`, and the omission was not a decision — it was left over from the version before,
where the crew only rehearsed and had nothing to undo.

The gap shows up in one state: a `$batch` that half-lands. The executor already detects it —
`PARTIAL`, because verifying only the record's own key would call a half-applied changeset a
success — and the crew's own handover said the substrate *"needs a rollback from the snapshot"*.
Nothing the crew controlled could perform one. An unattended run could therefore leave a
customer's system in a state nobody designed, and then ask a person to notice.

## Decision

**Undoing costs the same capability as writing.** `sys_rollback` requires `WRITE_TARGET`, exactly
like the write and the transport hop, because ADR-0009 already settled that the direction of a
change is irrelevant to the invariants. Ring 3 cannot undo any more than it can write.

**The operator undoes a half-landed batch, and only that.** A clean write is never rolled back; a
refused or dry-run step has nothing to undo. `PARTIAL` is the one case where doing nothing is
worse than acting, and it is squarely the operator's stated objective — minimise execution risk.

**It is the same rollback the console's button performs.** `execution.rollback_step` is the single
implementation, wearing the arming gate, the registry check and the executor's refusal to restore
an empty snapshot. The crew gets no shorter path to a customer's system than a person has.

**The rows come from the platform's own snapshot.** The crew's `sys_extract` now calls the same
`snapshot_step` the console does, which holds the rows server-side keyed by engagement and step.
A rollback that restored anything else would be an arbitrary write wearing a snapshot's name —
the substitution the chained ledger exists to make impossible — and a crew that snapshotted by
some other route would arrive at the undo with nothing to restore.

**A refused undo is said loudly.** If the restore itself fails, the step keeps its `PARTIAL`
status, carries the refusal verbatim, and the handover names an operator *now* and says the system
is in a state nobody designed. The platform cannot fix that; it can refuse to be quiet about it.

## Consequences

- The blast radius ADR-0020 accepted is bounded on one more side: the failure mode most likely to
  hurt a customer now self-corrects to a state the platform fingerprinted moments earlier.
- `_BEFORE` matters more than it did. It lives in process memory, so a restart between a write and
  its undo loses the rows — the safe direction (nothing is restored from a guess), and one more
  reason the arming window in ADR-0021 is short.
- A rolled-back step reads as neither done nor broken. The handover says exactly that: the
  rejected operations need a look before it runs again.

## Alternatives rejected

*Leave the undo to a person.* What the code did. It assumes somebody is watching an unattended
run, which is the assumption the word "unattended" denies.

*Roll back any failed write, not just a partial one.* A `FAILED` step wrote nothing — there is
nothing to put back, and restoring a snapshot over an unchanged system is a write nobody needed.

*Give the crew a wider undo: reverse a transport, re-open an approval.* Neither is a rollback.
Backing a transport out of production is a new change with its own authorisation, and an approval
is a person's act that no machine may reverse.
