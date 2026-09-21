# ADR-0025 — Controls are predicates over the whole population

Status: Accepted
Date: 2026-09-21
Relates to ADR-0002 (hash-chained ledger), ADR-0023 (assurance), invariants 4, 5 and 6.
Completes E11's C6.

## Context

A control is normally prose in a binder, and evidence is assembled toward it once a year by
somebody sampling forty rows out of eleven thousand. The sample is not a methodological nicety —
it is a consequence of the population being unreadable. Nobody can test every change in an SAP
estate because nobody can enumerate them.

Here they are enumerable. Every act that touched a customer's system is on the chain, or it did
not happen through this platform at all, and ADR-0023 already proved the chain can be counted.
Controls are the other half of C6: the same evidence, read as logic instead of prose.

## Decision

**A control is a predicate over the ledger, and it returns its violations.** Not a count, not a
top ten — the rows, each with its task, actor, timestamp and the sentence saying what is wrong
with it. A control that cannot show you its violations is prose again.

Six ship, each one an invariant this platform already enforces, now testable after the fact by
somebody who does not trust the enforcement:

| control | must be true |
|---|---|
| C-EXE-01 | every live write was preceded by a snapshot of the state it replaced |
| C-SOD-01 | no approval was given by the person who performed the work |
| C-ARM-01 | every live write was armed by somebody other than the person who spent it |
| C-DEC-01 | every one-way decision was resolved by two distinct named approvers |
| C-TRN-01 | every released transport reached production |
| C-REG-01 | no write reached a system that may not hold write credentials |

**"Nothing to test" is not a pass.** A control over an empty population returns `NOT_EXERCISED`.
The difference between "we checked and it held" and "there was nothing to check" is the first
thing an auditor asks about and the easiest thing for a dashboard to blur.

**Position is part of the predicate.** C-EXE-01 asks whether a snapshot was *already* on the chain
when the write was recorded, not whether one exists anywhere — a snapshot taken afterwards proves
nothing about what was replaced, and a membership test would have passed it.

**The control module is the authority on nothing.** The set of write-locked systems comes from the
registry, passed in by the caller. A control that decided for itself which systems were read-only
would be checking its own opinion.

## Consequences

- The controls are a second line, not the first. A real self-approval never reaches C-SOD-01,
  because `Ledger.approve` refuses it — so on a healthy engagement that control reads
  `NOT_EXERCISED` far more often than `PASS`, and that is the correct reading rather than a gap.
- They run on demand over the whole chain and cost a pass through a list, so they can be read as
  often as anybody likes. Continuous monitoring here is not an architecture, it is a `GET`.
- The Evidence screen loads them with the bundle rather than behind a button: an auditor reading
  the evidence is asking exactly the question the controls answer.
- Adding a control is adding a predicate and a population. The statement is prose a non-engineer
  can check, which is deliberate — the control is also the control narrative.

## Alternatives rejected

*A rules DSL with a parser.* A configuration language would let a client write controls without
Python, and buy a parser, a validator, an error-reporting surface and a security review. Six
predicates in the language the ledger is already written in is where this belongs until somebody
outside the codebase actually needs to write the seventh.

*Store control results.* They are a projection over an append-only chain: recomputing is cheap
and cannot disagree with its source, while a stored result can and eventually does.

*Report a pass rate.* A "5 of 6 controls passing" headline invites exactly the averaging that
ADR-0023 refused for assurance. A failing control is a failing control; the others do not dilute it.
