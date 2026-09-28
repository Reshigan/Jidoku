# ADR-0029 — The handover addresses a person, or says it cannot

Status: Accepted
Date: 2026-09-21
Relates to ADR-0027 (the night shift), ADR-0008 (roles come from the IdP). Delivers E12's
person-profile item, from M4 of docs/JIDOKA_TEAM_MEMBER_MODEL.md.

## Context

The night shift's handover named roles: *whoever makes the change*, *whoever owns this control*,
*a consultant at the keyboard*. Honest, and useless. A request addressed to nobody is a request
nobody answers, and a colleague who left notes for "whoever" would not be one for long.

M4 is specific about what fixes it, and equally specific about what must not be invented: people
have authority, capacity, latency and working hours, and the platform routes to the *cheapest
sufficient authority* while respecting the clock.

## Decision

**People are declared, never inferred.** `POST /engagements/{eid}/people` takes a team: name,
authority, cost, working hours, timezone, days, capacity. Cost is what the organisation
says an hour of that person's attention is worth to the programme — a platform that guessed at
somebody's seniority would be guessing about a person.

**Authority is written in the platform's own permission names.** `approve`, `resolve_dp`,
`execute`, `arm`. So "who may resolve a statutory decision" is checked against the same table the
API gates on rather than against a job title, and a typo is a 422 at registration instead of an
ask that silently routes to nobody.

**The cheapest sufficient authority, not the most senior available.** The least senior person
registered who may sign the thing. Spending a partner on a decision a team lead could make is how
approval queues form — and a tie on cost breaks by name, so routing is the same on every run.

**Availability changes when, not who.** Swapping to a more expensive person because the right one
is asleep is how a programme teaches itself to wake partners. A routine ask outside somebody's
hours says when they will see it; an ask whose cost of silence is above the interruption threshold
goes now regardless, because at that price the person would rather be woken (ADR-0027 already
prices this).

**Capacity changes who; being slow never does.** What each person has already been asked this
week is read off the ledger — the night writes an `ASKED` entry per person per thing, and the same
unanswered question found on five consecutive nights is one thing they owe, not five. Somebody at
the capacity their organisation declared is passed over for the next cheapest sufficient
authority, and when everybody who could sign it is full, nobody is asked and the queue is the
finding. Observed latency is the opposite case: it is computed from the ledger's
`DP_RAISED`/`DP_RESOLVED` pairs and printed in the reason the handover gives — *"they have
answered in 72h on this engagement"* — and it is never an input to routing. Quietly reassigning
somebody's work on the strength of a median is an organisational decision the platform has no
standing to make, and the person routed around would never know it happened.

**The clock is a named zone, not an offset.** `tz` is an IANA name, so working hours move with
daylight saving rather than being right eleven months of the year. An unknown name is a 422 at
registration, next to the unknown-authority refusal and for the same reason. `utc_offset` remains
as the fallback for a team that has not named a zone and for an image with no tz database, and
`jidoka-os` depends on `tzdata` so the second case is the deployer's choice rather than an
accident.

**Nobody to ask is the finding.** With no team registered the handover names the role exactly as
before — no pretence that somebody was asked. Where a team exists but nobody in it holds the
authority, the handover says *"(nobody I can ask)"* and names the permission that is missing.

## Consequences

- The handover reads like a colleague's note: *"A. Silva — at Mon 08:00 their time: the CSDM
  change is still not in the system"*.
- The ledger carries a new action, `ASKED`. It is a projection input like every other entry —
  capacity is recomputed from the chain rather than stored — and it is written only for asks that
  reached a registered person, because a finding addressed to a role consumed nobody's week.
- A night spends capacity on its own findings as it routes them, costliest first. So when
  somebody fills up mid-night, what goes unasked is what mattered least, and a batch that ignored
  its own effect on the week cannot hand one person everything it found.
- `GET /engagements/{eid}/people` reports `asked_this_week` and `answers_in_hours` beside the
  declared team. The console prints both on the night-shift card, so a queue behind one name is
  visible before it bites.
- A handover the router could not place now says *"(nobody I can ask)"* and gives the reason,
  where before it printed the fallback role and hid the refusal. A bottleneck printed as an ask
  is a bottleneck hidden.
- Latency is measured and shown and does nothing. That is the decision, not an omission: see
  above. If a programme wants slow approvers routed around, a human changes `cost` or the team.

## Alternatives rejected

*Derive authority from the IdP groups.* ADR-0008 maps groups to roles already, and it is tempting
to reuse that as the team. It would conflate two different questions — what someone is permitted
to do, and whether the platform should ask *them* rather than a colleague who costs less. The
first is security; the second is manners.

*Route to everyone who could answer.* A broadcast is the absence of a routing decision, and it
trains a team to ignore the platform.

*Infer cost from role.* An approver is not automatically more expensive than a builder, and a
platform that assumed so would be making an organisational claim it has no standing to make.
