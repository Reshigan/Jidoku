# ADR-0020 — A crew may spend an arming it can never grant

Status: Accepted
Date: 2026-09-20
Supersedes the "stops at a rehearsal" position in ADR-0018. Relates to ADR-0005 (arming is a
second person's act), ADR-0006 (transport-aware completion), ADR-0009 (transport advancement is a
write path), invariants 3, 4, 6 and 7.

## Context

ADR-0018 shipped a crew that took an engagement to the first human gate and stopped: every
Tier-A step came back a rehearsal because the operator dispatched every write with `armed=None`.
That was the safe first version and it was explicitly chosen over the alternative, which the ADR
recorded as rejected for the time being: *let the crew arm a pre-armed target.*

It was rejected on a judgement, not a principle — "the gap between a person armed this and an
unattended process wrote to a tenant an hour later is where a real incident lives". The platform's
owner has since asked for the opposite, in plain terms: the team does the transactions, and the
team does the actual configuration of the system. That is a decision about risk appetite, and it
belongs to the person carrying the engagement rather than to the ADR that anticipated it.

What matters is that the invariants do not move. They do not.

## Decision

**The crew spends an arming. It can never grant one.**

`_ARMED` is written by exactly one endpoint, `POST /execution/arm`, which `approver` holds and
`builder` does not (`auth.ROLE_PERMISSIONS`, asserted at import). No syscall arms anything — a
test asserts no name in `SYSCALL_TABLE` contains "arm" — so there is no path from an agent's
reasoning to an armed target, whatever it decides.

**The operator calls the console's own code.** `execution.execute_step` is now the single
implementation of the apply path, called by the Work board's Execute button and by
`sys_write_tier_a`. The crew does not get a second copy of the gates, because two copies of a
gate are one gate and one bug waiting to happen. Consequently:

- no arming → a dry run, whoever asked (invariant 6);
- an arming whose `armed_by` is the actor running the step → refused in the executor's own words,
  and the refusal is reported as the step's outcome rather than raised into the run (invariant 7);
- no `SNAPSHOT` on the task's chain → refused (invariant 4);
- a write-locked target → refused by the registry (invariant 3).

**The operator carries an ABAP change to production.** ADR-0006 says a verified write on the ABAP
stack is `IN_TRANSPORT`, not done. `sys_advance_transport` costs `WRITE_TARGET`, the same
capability as the write itself, because ADR-0009 already established that advancing a transport is
a write to a customer's landscape. The operator walks the route one legal hop at a time, bounded
by the route's own length — a loop that trusted the substrate to say "no next hop" would spin
forever the first time a substrate lied — and stops on the first refusal, naming who owns it.

A transport exists only because an armed write was captured in it, and the route came from the
promotion paths a human declared at system registration. So moving a change along it completes an
authorised write; it does not create a new authority, and the crew cannot propose a route.

**The crew still cannot approve.** `APPROVE` exists in no ring an agent can occupy, and a written
step's handover line now reads "a reviewer who did not build it" — invariant 4 wants a second
person, and the crew is never one. A run that configures a whole landscape still ends unapproved.

## Consequences

- An unattended run can now change a customer's production system, end to end, where an approver
  has armed the target first. That is a real increase in blast radius and it should be read as
  one: the andon cord, the arming endpoint and the role table are what bound it.
- Arming is the control surface that matters now. `_ARMED` lives in process memory and dies with
  it, which is the safe failure direction — a restart disarms every target rather than leaving one
  primed for the next run.
- The Crew screen had to stop saying "every Tier-A write is a rehearsal", because it is no longer
  true. Status colour now answers the question an operator is actually asking — did we change
  production — and each ABAP row prints the hops its change has taken.
- ADR-0018's table of what the crew may do is amended: the operator writes and transports rather
  than only rehearsing. Everything else in it stands.

## Alternatives rejected

*Require a second, crew-specific arming.* A gate that exists only for the machine, stricter than
the one a person passes through for the identical act. It would have looked prudent and taught
operators that the crew's writes are a different kind of write, which is exactly the confusion to
avoid: it is the same write, through the same executor, under the same arming.

*Let the crew arm when the run's caller holds `approver`.* This is the invariant-7 hole wearing a
convenience: the same human would be arming and spending in one call, which is what
`armed_by != actor` exists to prevent. The executor would have refused it anyway, and building a
path whose only outcome is a refusal teaches nobody anything.
