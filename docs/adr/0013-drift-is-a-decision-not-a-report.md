# ADR-0013 — Drift is a decision, not a report

Status: Accepted
Date: 2026-09-01
Relates to invariants 1, 2, 4; ADR-0001 (signed IR), ADR-0002 (hash-chained ledger).

## Context

Every configuration platform meets the same moment: the live system disagrees with the recorded
intent. Someone changed a value in Admin Center on a Friday; a support ticket "fixed" a picklist;
a parallel project transported over ours. The industry has two standard answers and both are
wrong:

- **Auto-remediate** ("desired state wins"): re-apply the intent. This overwrites a change nobody
  has understood yet. If the Friday change was a statutory correction, re-applying the old value
  is not hygiene, it is a compliance incident executed by a robot.
- **Auto-adopt** ("observed state wins"): update the record to match the system. This launders an
  unsigned change into the system of record, which under invariant 1 is exactly the thing this
  platform exists to make impossible. Intent that nobody signed must never become intent.

Both answers share a premise: that drift is a technical inconsistency to be resolved by machinery.
It is not. Drift is the discovery that two authorities disagree — the signature on the IR and the
hands on the live system — and choosing between authorities is a human act.

## Decision

`jidoka_core.drift.DriftWatch` is the only drift path, and its whole API is `observe()`.

- A verification that finds MATCH is ledgered `VERIFIED`.
- A verification that finds DRIFT or MISSING is ledgered `DRIFT_DETECTED` (fields, both values,
  system) and raises a blocking DESIGN decision point `DP-DRIFT-<key>`, owned by the signer of
  the drifted record, with exactly two options: **reassert signed intent** (re-apply the IR
  record) or **adopt observed state** (sign a new IR record that says so). There is no third
  option and no default.
- The decision point blocks planning through the same gate as an IR gap (invariant 2).
  `DecisionEngine.unresolved()` feeds the planner; the API merges it into `plan()`'s block set,
  so no client can plan over unexplained drift.
- Repeated observation of the same drift does not stack decision points; the open one stands.
- A MATCH observed while a drift DP is open does **not** close it. A self-healing anomaly is an
  anomaly with better timing: the live system now agrees, but the change that made it disagree is
  still unexplained. The ledger entry says so, and the question stays with its owner.
- The watch has no `reconcile`, `heal`, `sync`, `reapply` or `adopt` method, and a test asserts
  their absence. Reasserting intent goes back through the full execution path (arm, snapshot,
  approve); adopting goes back through signed IR upload. Both exits re-enter the front door.

## Consequences

Verification is safe to run continuously, because running it can never write to a live system and
never mutates intent — the worst it can do is raise a question. The verification report
(`jidoka_compiler.project.verification_report`) is a projection of this machinery: the test plan
is the signed intent itself, results are read off the ledger, and an object never verified is
listed as a finding rather than shown green.
