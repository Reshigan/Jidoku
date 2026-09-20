# ADR-0021 — An arming is a window, and a handoff is a chase

Status: Accepted
Date: 2026-09-20
Relates to ADR-0003 (native substrates only), ADR-0005 (arming), ADR-0013/0019 (drift),
ADR-0020 (the crew spends an arming), invariants 2, 4 and 6.

## Context

Two loose ends from ADR-0020, both of which only became load-bearing once an unattended crew
started spending armings and producing artefacts.

**How long is an arming live?** `_ARMED` lives in the API process and dies with it. That was
described as the safe failure direction, and it is — but it means the answer to "how long does
this authority last" was *whenever someone next deploys*. Nobody chose that, nobody can see it,
and it is simultaneously too long (an arming from this morning is still live this evening) and
too short (a cutover spanning a deploy silently loses every arming mid-flight). The obvious fix
— persist armings so they survive a restart — makes the first problem worse to fix the second.

**Who chases a person's work?** Tier B and C exist because SAP publishes no write path for those
objects (ADR-0003), so the platform emits an artefact and a person does the work by hand. Nothing
then asked whether they had. Worse, ADR-0019's rule filed those records under NOT_APPLIED —
"nobody has built it yet" — which is true of a record nobody has been asked to build and quite
wrong about one whose instruction sheet went out an hour ago.

## Decision

**An arming carries the moment it lapses.** `ArmedTarget` gains `expires_at`, and the executor
refuses a lapsed one in the same place it refuses every other arming failure, naming when it
lapsed — an operator reading that has to decide between re-arming and finding out what took so
long, and those are different actions. The API sets a window on every arming: 60 minutes by
default, at most 12 hours, an approver may ask for less. The window is on the ledger entry, in
the endpoint's response, and on the Configure card. A lapsed arming is not listed as armed,
because the console must never offer a write the executor is about to refuse.

Armings still do not survive a restart, and now that is a smaller fact rather than the whole
policy: the window is the policy, and the process lifetime is only ever shorter than it.

**A handoff is chased, from evidence.** `DriftWatch.observe` takes `progress` — WRITTEN,
HANDED_OFF or UNTOUCHED, read off the ledger — and an absence from the live system means three
different things accordingly. HANDED_OFF plus absent is `AWAITING_A_PERSON`: the platform did its
half and the work is outstanding. Verification returns those separately, with the date the
artefact went out, and the crew's handover carries them.

The chase is built from the live system and the ledger, never from the plan. A chase written from
the plan keeps asking for work somebody finished an hour ago; this one stops the moment a
re-read finds the record, which is the whole Tier-C bargain in ADR-0003 — a person does it, and
JIDOKA verifies it.

**Outstanding human work never blocks the plan.** It raises no decision point. Invariant 2 is for
values nobody may guess; a decision point here would stop the line over somebody's inbox.

## Consequences

- The question "should armings survive a restart" is answered by making it matter less. If a real
  cutover needs a longer window, an approver asks for one and it is on the chain; if a deploy
  lands mid-window the arming is gone, and re-arming is a deliberate act by a named person, which
  is what it was in the first place.
- `NOT_APPLIED` now means what it says: nobody has been asked to build this. The Tier-C record in
  the Komatsu fixture moved out of it, which is why two tests changed.
- The Crew screen counts "with a person" beside "not built yet" and "unexplained differences".
  Three absences, three different meanings, three columns — folding them together is what made
  the Verify screen misleading in the first place.
- A Tier-C object the adapter cannot read is chased forever, because JIDOKA cannot see it done.
  That is a dishonest tier map rather than a bug here: ADR-0003 says a Tier-C object must be
  verifiable by extract-diff, and one that is not should never have been mapped Tier C.

## Alternatives rejected

*Persist armings across restarts.* The thing that made a restart tolerable was that it revoked
authority. Persisting it without a window would have left standing authorisations that no one
reviews, spent by a machine, which is precisely the risk ADR-0020 took on knowingly and should
not quietly deepen.

*Raise a decision point for outstanding Tier B/C work.* It reuses machinery that already exists,
and it blocks planning on the fact that a person is busy. Decision points are for questions with
answers nobody may guess. "Has Thandi done the data model change yet" is a question with an
answer the live system already holds.

*Escalate after N runs.* Attractive and unbuildable honestly today: the crew has no model of who
owns a Tier-C step beyond "a consultant at the keyboard", and escalating to an unnamed person is
theatre. The handover carries the date; `jidoka-os`'s cost-of-silence scheduler is where this
belongs once person profiles exist (E12).
