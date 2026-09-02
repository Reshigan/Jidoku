# ADR-0015 — Attestations are written by the act, not claimed by the caller

Status: Accepted
Date: 2026-09-02
Relates to ADR-0002 (hash-chained ledger), ADR-0005 (arming), invariants 4, 6 and 7.

## Context

Invariants 4 and 6 are enforced by reading the ledger back:

- `Ledger.approve` refuses when the reviewer appears as the `actor` of an `EXECUTED` entry on the
  task, and refuses when the task carries no `SNAPSHOT`.
- `Executor._assert_snapshot` refuses a live write when the task carries no `SNAPSHOT`.

Both read an *action string* and trust it. `POST /engagements/{eid}/ledger` accepted any action
string from any caller holding `ledger_append`, and `POST /engagements/{eid}/phase` accepted an
`actor` from the request body. So a caller could manufacture its own permission:

- forge `SNAPSHOT` and a live write passes the rollback gate having read nothing back, so a
  rollback restores a "before" state that was never captured;
- forge `EXECUTED` under the approver's name and that approver is locked out of their own task
  (a denial-of-approval, and a false record of who touched the system);
- forge `APPROVED` and the evidence bundle attests a separation of duties that never happened.

The console did the same thing from the client side: the Work board's "Take before-snapshot",
"Execute" and "Roll back" buttons posted ledger rows instead of calling the endpoints that
perform the act. That is the more dangerous half — it records executions that never touched a
system, and the evidence bundle cannot tell the difference.

## Decision

**A ledger action that the kernel writes as proof of work is never accepted from a caller.**

`routers/ledger.py` holds `RESERVED_ACTIONS` — `SNAPSHOT`, `EXECUTED`, `APPROVED`, `ARMED`,
`DISARMED`, `ROLLED_BACK`, `PHASE_ADVANCED`, `DRY_RUN` — and refuses them with 403, case-insensitively,
pointing the caller at the endpoint that performs the act. Free-form annotations (`NOTED`,
`VALIDATED`) stay open: they are a person's remark, not a machine's attestation.

**Every entry is signed by the token holder, never by a name in the body.** `Entry` has no `actor`
field and `PhaseIn.actor` is gone; both routers pass `identity.subject`. An entry naming someone
who did not hold the token is a forged attestation regardless of intent.

**The console asks the endpoint that does the work.** `App.tsx`'s `stage` routes `SNAPSHOT`,
`EXECUTED` and `ROLLED_BACK` to `platform.snapshot`, `platform.execute` and `platform.rollback`.
The server writes its own attestation after the act, under the caller's own identity, having
actually read or written the system. Only `VALIDATED` still appends — a person saying they read
it back is an annotation and signs itself.

## Consequences

- The ledger's action vocabulary is now split in two: kernel-written proof, and caller-written
  remark. Any new gate that reads an action back as a precondition must add that action to
  `RESERVED_ACTIONS` in the same change, or it inherits this hole.
- Tests that seeded `SNAPSHOT`/`EXECUTED` over HTTP now seed through the kernel
  (`get_or_404(eid).ledger.append`), which is the only thing permitted to write them.
- `test_phase_advance_is_ledgered` asserted the old forgeable behaviour — it asserted the bug — and
  now asserts the opposite: a supplied `actor` is ignored.
- Invariant 7 gets a second layer. A builder could previously write `APPROVED` directly; now the
  only path to that action is `ledger/approve`, which runs the SoD check.

## Alternatives rejected

*Sign entries and verify the signature.* Correct eventually, but it does not help here: the
attacker holds a legitimate token. The problem is not who signed, it is that a signature was
accepted as evidence of an act nobody performed.

*Let the kernel refuse reserved actions in `Ledger.append`.* That is where it belongs, but the
kernel's own executor and approver call `append` with exactly those actions. Splitting `append`
into a privileged and unprivileged half is a larger change than the transport-layer gate, and the
transport is where untrusted callers actually arrive. Revisit if a second client appears.
