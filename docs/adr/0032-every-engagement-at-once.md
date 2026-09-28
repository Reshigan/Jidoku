# ADR-0032 — Every engagement at once, and the same numbers its own screen shows

Status: Accepted
Date: 2026-09-21
Relates to ADR-0028 (a clock in both deployment shapes), ADR-0030 (a night that did not run
reports itself), ADR-0031 (the platform keeps its own record).

## Context

The night shift has iterated every engagement on the kernel since ADR-0028. Its summary went to a
log line and an exit code, and nothing else in the platform had ever looked at more than one
engagement at a time.

So the question a partner running eleven programmes actually asks — *which of these needs me
today* — was answerable only by opening eleven screens and forming the answer by hand, weekly, and
being wrong about it in between. The failure this creates is specific and quiet: a programme
nobody has opened in three weeks looks exactly like one that is going well.

## Decision

**A roll-up, and not one number of its own.** `GET /portfolio` runs the same projections each
engagement's own screen runs: the clock off the ledger, the assurance fraction, the statutory
decisions that hard-block planning, the refusals still standing. Nothing is recomputed differently
and nothing is averaged across engagements. A roll-up with a second opinion is an argument, and
the first item in every steering meeting would be which number is right.

**One line per engagement, worst first, and only the worst thing.** A row that says three things
says none of them. The order is the night shift's reasoning applied to a list: a broken chain
outranks a statutory block outranks a clock that has stopped, because that is the order in which
they cost the programme.

**`needs_a_person` is a sentence, not a status.** "3 statutory decision(s) are blocking the plan,
and JIDOKA will not invent them" is actionable; AMBER is a colour somebody has to decode.

**Read access, not a partner role.** A roll-up only the most senior person can open is one that
gets screenshotted into a slide once a month and is wrong by the meeting.

## Consequences

- An engagement nobody has touched is now on the list rather than absent from it, and its silence
  is stated as a finding.
- The endpoint reads every engagement's whole chain on each call. That is the same cost the
  engagement screens already pay, multiplied by the number of engagements, and it is a read: the
  first kernel where it hurts should cache the rows, never precompute them into a store that can
  disagree with the chain.
- There is no cross-engagement aggregate — no portfolio-wide "proven" percentage. Averaging
  assurance across programmes of different sizes and phases produces a number that moves for
  reasons nobody can name, and it would be the number that got quoted.

## Alternatives rejected

*A tenant dashboard with its own store.* A second copy of every fact, updated on a schedule,
disagreeing with the ledger between updates. Every projection in this platform reads the chain for
the same reason.

*A traffic light per engagement.* Colour without a sentence trains people to read the colour, and
the sentence is where the actual information is.
