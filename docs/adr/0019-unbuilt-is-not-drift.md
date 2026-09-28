# ADR-0019 — Unbuilt is not drift

Status: Accepted
Date: 2026-09-20
Amends ADR-0013 (drift is a decision, not a report). Relates to invariant 2.

## Context

ADR-0013 says a live value that signed intent does not explain becomes a ledger entry plus a
blocking decision point owned by a named person, with two exits: reassert the signed intent, or
sign new intent adopting what is there. That is right for a system somebody has configured.

`DriftWatch` applied it to one more case that is not that case. A record in signed intent that
has never been built is absent from the live system, `verify()` returns MISSING, and the watch
raised a blocking decision point asking whether to reassert or adopt. Both answers are wrong. The
real answer is "build it" — and neither exit says so, so the decision sat open and planning
stayed blocked (invariant 2, working exactly as designed, on a question nobody should have been
asked).

The effect was that pressing Verify on a fresh engagement raised one blocking decision per record
and stopped the plan. It went unnoticed because the test suite asserted it: a test named
*a missing record raises a blocking decision point* set the behaviour down as intended. The crew
run (ADR-0018) made it impossible to ignore — a run ends by verifying, so every run blocked the
next one, and the feature could be used exactly once per engagement.

## Decision

**Only a record this platform has written can drift.** `DriftWatch.observe` takes `applied`, and
verification derives it from the ledger: an `EXECUTED` entry on that record's chain, which is the
only thing that means a write happened.

- absent **and** never written → `NOT_APPLIED`, a ledger entry, no decision point. It is unbuilt
  work, and the plan is what closes it.
- absent **and** written → drift, exactly as ADR-0013 says. We put it there and it is gone.
- present but disagreeing → drift, written by us or not. A record nobody built that exists anyway
  is the most interesting finding on the page: somebody configured it outside this platform.

Verification returns `not_applied` as its own list, so the console can say "not built yet" in the
words that are true rather than folding it into a drift count.

## Consequences

- Verify on a fresh engagement is usable: it reports what is not built, raises nothing, and leaves
  the plan alone.
- ADR-0013's gate is narrowed to what it always described and is otherwise untouched: no reconcile
  path, no adopt-by-default, and a re-matching system still keeps its question open.
- `test_a_missing_record_raises_a_blocking_decision_point` asserted the defect. It is now two
  tests — one for absence after a build, one for absence before it — and a third for the record
  that exists though nobody built it.
- `NOT_APPLIED` counts as "looked at" when the crew's auditor asks which records have never been
  checked. The platform read the live system and returned a verdict; objecting that nobody has
  ever looked would be false.

## Alternatives rejected

*Let the crew skip verification.* It would have hidden the defect behind the feature that exposed
it, and left the Verify button broken for everyone else.

*Raise the decision point but do not block.* A decision point that does not block is a warning,
and ADR-0013's whole argument is that warnings decay while gates do not. The fix is to not ask a
question with no right answer, rather than to weaken what asking one means.
