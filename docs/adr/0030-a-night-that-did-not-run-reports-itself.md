# ADR-0030 — A night that did not run reports itself

Status: Accepted
Date: 2026-09-21
Relates to ADR-0027 (the night shift), ADR-0028 (a clock in both deployment shapes), ADR-0029
(the handover addresses a person).

## Context

The night shift is the platform's claim to being a colleague rather than a tool: it works while
nobody is watching and the morning opens with a handover. ADR-0028 gave it a clock in both
deployment shapes — `python -m jidoka_api.nightly` under compose, a Worker `scheduled()` handler at
the edge.

The edge clock calls the kernel with `NIGHT_TOKEN`, a Worker secret a human sets by hand. When it
is absent the handler refuses loudly and logs *"no night was worked"* — which was the right
behaviour and the wrong assumption about who is listening. Nobody tails a Worker log at 02:00. A
platform set up exactly as documented would have deployed cleanly, fired its cron every night,
refused every night, and looked correct from every surface a person actually opens.

Worse, the last handover was held in a process dictionary. A kernel restart made
`GET /engagements/{eid}/nightshift` report that no night had ever been worked on an engagement
that had been worked every night for a month — so the one surface that could have shown the
silence was already lying in the other direction.

The general shape: **nothing inside a night can report its own absence.** A rotated token, a cron
that is not firing, an edge that was never deployed, a kernel the edge cannot reach — every one of
them is invisible from inside the run that did not happen.

## Decision

**The chain reports it.** The night writes a `HANDOVER` entry on every run, so whether a night
happened is already a fact about the ledger. `jidoka_os.handover.clock()` is a projection over it,
like assurance, the controls and twin fidelity: last run, hours of silence, and whether a night has
been missed. `SILENT_AFTER_HOURS = 36` is published — generous enough that a late run is not an
alarm, tight enough that two missed nights cannot pass unnoticed.

**The console says it before it says anything else.** `GET /engagements/{eid}/nightshift` carries
the clock, and the Crew screen prints the silence above the handover with a stop lamp. A stale
handover read as this morning's is the failure this prevents, so the warning comes first, not as a
footnote under it.

**Memory holds the text; the ledger holds the fact.** The last handover stays in process memory —
it is a rendering convenience and losing it costs nothing. Whether a night ran is never read from
there again.

**The edge answers for itself at publish time.** `GET /__edge` reports `kernel_url`, `night_token`
and `night_armed` as booleans, never values: the point is to catch a secret that was never set or
has since been rotated, and printing it would be the leak the check exists to prevent. Asked the
minute a deploy finishes, it turns a silent first night into a failed deploy check.

## Consequences

- A missed night is visible on the screen the crew already opens, with the three causes named and
  an honest admission that nothing here can tell which one it is.
- `/__edge` is unauthenticated, like `/health`. It discloses that two settings exist and nothing
  about what they are. An authenticated readiness check that nobody can call before the first
  sign-in is a readiness check nobody runs.
- The 36-hour threshold is a guess about one deployment's schedule dressed as a constant. It is
  published rather than hidden so a programme on a different cadence can argue with it — but a
  per-engagement schedule would be the honest version, and this is not that.
- The clock says a night *ran*, not that it ran *well*. A night that worked every engagement and
  found nothing looks identical to one that failed on all of them after writing its handover;
  `nightly.py`'s exit code is what distinguishes those, and only the compose-shape clock reads it.

## Alternatives rejected

*Alert from the Worker.* A `scheduled()` handler that emails or pages on a missing secret puts an
outbound notification channel at the edge, needs its own credential, and fails exactly when the
thing it is reporting on has failed. The platform already has a surface people read.

*Store the last-run timestamp.* A second copy of a fact the ledger already holds, and the first
thing to drift. Every other verdict in this platform is a projection over the chain; this one has
no reason to be different.

*Have the night write "I did not run".* It cannot. That is the whole problem.
