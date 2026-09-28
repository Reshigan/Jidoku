# ADR-0018 — A crew runs the engagement, and stops at every human gate

Status: Accepted
Date: 2026-09-20
Relates to ADR-0004 (agent OS), ADR-0005 (arming), ADR-0015 (attestations), invariants 2, 6 and 7.

## Context

`jidoka-os` has described an operating system for agents since the first commit: four rings, a
capability ceiling per ring, a syscall table that assigns a capability to every call, budgets,
a supervisor, an andon cord, and an economy of five agents with opposed objectives. ADR-0004
argued the case — "tool lists are not a security boundary, they are a suggestion to a model" —
and the tests proved the gates in isolation.

`Kernel.register` had no caller anywhere in the platform. Every handler was a test's. A kernel
with no handlers is a security model nobody can run, and an economy nobody spawns is a diagram.
Meanwhile the thing the product is for — take an engagement and do the work — had no entry point
at all: a person clicked snapshot, then execute, then verify, one record at a time, forever.

The obvious build is an LLM agent with a tool list. That is the thing ADR-0004 already rejected,
and it would have been untestable here besides: no key in CI, non-deterministic, unprovable.

## Decision

**Five agents, each holding only what its ring permits, running one pass over the engagement.**
`jidoka_os.crew.run` spawns the economy and acts through `kernel.dispatch` and nothing else. The
division of labour is the capability table, not a convention anybody has to remember:

| agent | ring | can | so it |
|---|---|---|---|
| statutory-sentinel | 2 agent | read, raise_dp | asks about values nobody may guess |
| architect | 2 agent | read, plan, emit, ledger_write, raise_dp | sequences the work and emits the artefacts |
| operator | 1 service | read, plan, write_target, ledger_write | snapshots and rehearses every Tier-A write |
| auditor | 3 untrusted | read, halt | objects, and can write nothing at all |
| economist | 3 untrusted | read, halt | prices the delta pool |

The operator cannot emit an artefact because ring SERVICE was never granted EMIT. The auditor
cannot record its own findings because ring UNTRUSTED holds READ_SYSTEM and HALT. No agent in
any ring can approve, because APPROVE exists in no ring an agent can occupy — a module-level
assertion in `capabilities.py`, not a review comment.

**The handlers are the console's own code path.** `routers/run.py` binds each syscall to the same
executor, registry and ledger the Work board's buttons use. The crew gets the operator's route to
a customer's system, not a faster one, and with less authority.

**A run ends in a handover.** Every Tier-A step is dispatched with `armed=None`, so the executor's
own gate makes it a dry run (invariant 6); the crew has no way to arm because no agent ring holds
the authority. `sys_ledger_approve` and `sys_resolve_dp` are deliberately left unregistered —
their capabilities are unreachable from ring 2 and below, so a handler for either would be
unreachable code that looks like a door, and one refactor away from being one. The report's first
section is `waiting_on_a_person`.

**Refusals are the product, not an error path.** A capability denial, a budget kill, a halted line
and a handler's own refusal are recorded in the agent's card and the run continues with the agents
that still can. A crew that fell over on the first gate would be useless on a real engagement,
where gates fire constantly.

**The sentinel never re-asks an answered question.** `raise_dp` overwrites by id, so a second run
that re-raised a resolved decision point would silently erase a human's answer. Every existing
decision point id is passed in, and the sentinel skips them.

**Verification is the platform's act, not an agent's.** There is no verification syscall in the
table at all. The run calls the same pass the Verify screen calls — a platform with two
verifications has two truths, and the one nobody is watching is the one that goes stale.

## Consequences

- An unattended run does everything up to a human gate: sequences, snapshots, rehearses, emits,
  asks, objects, prices, verifies. It cannot write to a customer's system and cannot approve.
  This is the ceiling by design, and it is not raised by a braver release.
- The auditor's objections are now visible to a customer in the console. Some of them are about
  the crew's own output. That is the point of opposed objectives, and a run where the auditor
  finds nothing is a run, not a failure.
- The statutory sentinel blocks the first run on most real workbooks, because a leave accrual
  signed by a spreadsheet is exactly what invariant 5 is about. The marker list in `crew.py` is
  published for the same reason the scrubber's patterns are: a gate nobody can read is a gate
  nobody can argue with.
- `Kernel.register` has a production caller, so the ring model is now exercised by every run
  rather than only by its own tests.

## Alternatives rejected

*An LLM agent with a tool list.* ADR-0004 settled this: the reachable action set must not depend
on the model's reasoning being sound. The K5 consultant still has a place — judgement, rationale,
the objection somebody has to read — and it will run inside this, as a process in ring 2 with a
budget, not as the thing holding the keys.

*Let the crew arm a pre-armed target.* Legal under invariant 6 — an approver armed it, the crew
only spends it — and rejected anyway for now. The gap between "a person armed this" and "an
unattended process wrote to a tenant an hour later" is where a real incident lives, and nothing
about the design becomes harder by waiting for someone to ask for it.

*One agent doing all five jobs.* Cheaper, and it throws away the only property that makes the
report trustworthy: the auditor's objections mean something because the auditor could not have
written the thing it is objecting to.
