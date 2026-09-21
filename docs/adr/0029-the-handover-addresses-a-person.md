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
authority, cost, working hours, timezone offset, days, capacity. Cost is what the organisation
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

**Nobody to ask is the finding.** With no team registered the handover names the role exactly as
before — no pretence that somebody was asked. Where a team exists but nobody in it holds the
authority, the handover says *"(nobody I can ask)"* and names the permission that is missing.

## Consequences

- The handover reads like a colleague's note: *"A. Silva — at Mon 08:00 their time: the CSDM
  change is still not in the system"*.
- `capacity_per_week` is declared and not yet used. Capacity is the real bottleneck at scale, and
  spending it correctly needs a record of what each person has already been asked this week —
  which the ledger could support and this does not yet do. It is in the shape rather than in the
  behaviour, and saying so is better than dropping the field or pretending it works.
- Latency — M4's "observed decision speed" — is not modelled at all. It is learnable from the
  ledger's DP_RAISED/DP_RESOLVED pairs and nothing here learns it.
- Timezone is an integer offset, not a zone name, so it does not move with daylight saving. Real
  for the programmes this targets and wrong in March; a tz database belongs here the day somebody
  is actually missed by an hour.

## Alternatives rejected

*Derive authority from the IdP groups.* ADR-0008 maps groups to roles already, and it is tempting
to reuse that as the team. It would conflate two different questions — what someone is permitted
to do, and whether the platform should ask *them* rather than a colleague who costs less. The
first is security; the second is manners.

*Route to everyone who could answer.* A broadcast is the absence of a routing decision, and it
trains a team to ignore the platform.

*Infer cost from role.* An approver is not automatically more expensive than a builder, and a
platform that assumed so would be making an organisational claim it has no standing to make.
