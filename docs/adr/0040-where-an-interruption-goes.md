# ADR-0040 — Where an interruption actually goes

Status: Accepted
Date: 2026-09-22
Relates to ADR-0027 (the night shift and the interruption budget), ADR-0029 (routing to a named
person), ADR-0030 (the clock), invariant 7.

## Context

The night shift ranks every finding by what it costs to stay unsaid, spends a hard interruption
budget, picks the cheapest sufficient authority, checks their working hours in their own named
timezone, respects the weekly capacity their organisation declared, and reports how fast they have
answered before — and then put the result in a dictionary. `people.py` says so in its own
docstring: *nothing here sends anything, and nothing here knows what a notification is.*

Every piece upstream of a sink was built and tested. Without the sink, "I woke somebody three
times of three allowed" was not a true sentence, and the handover said it anyway.

## Decision

**One sink: an HTTP POST to a configured URL.** Slack, Teams, Opsgenie, PagerDuty and a script on
a box all accept one, so a webhook is the whole integration surface rather than three SDKs and
their transitive dependencies. Unset, nothing is sent and the night says so.

**Only what the budget spent.** `interrupted` is sent; `deferred` and `waited` are not. The budget
is the product — a colleague who talks less than they could is trusted more — and a sink that sent
everything would quietly undo it.

**The payload carries the least that is useful,** because it leaves the tenant: who is being
asked, what for, what it costs to stay quiet, and why them. No ledger hashes, no configured
values, no evidence, not even the finding's detail. A notification is a tap on the shoulder, not
an export.

**The URL is a credential.** Read in one place, never returned, logged, or included in an
exception message — the sink reports a failure by exception class, never by its text, for the same
reason the store's health check does.

**Every attempt is on the chain,** `NOTIFIED`, whether it worked or not. A sink nobody can see
failing is a sink everybody assumes is working.

**Failing to send never fails the night.** The handover is on the ledger either way. A night that
lost its work because a webhook was down would have traded the thing it is for the thing that
announces it.

**Only the night shift endpoint can send.** A test asserts it is the sole caller: an agent that
could notify could page a customer at will, and no ring the crew occupies has a channel to one.

## Consequences

- With no sink configured, the console says plainly that the interruptions had nowhere to go and
  nobody was told, rather than letting the budget's own wording imply somebody was.
- A webhook body is not encrypted beyond TLS and the receiving system is outside the ledger's
  reach. That is what keeps the payload minimal, and it is a reason to point this at an internal
  endpoint rather than a public chat by default.
- One sink for the whole kernel, not one per engagement. A per-tenant sink belongs with the
  per-tenant storage of phase 2, and shipping it before then would mean a second place for a
  tenant's configuration to live.

## Alternatives rejected

*SMTP.* A dependency, a credential, a deliverability problem and a queue, to reach an inbox that
is worse at 02:00 than a channel is.

*A Slack app.* One vendor, an SDK, a token with more scope than sending a message, and nothing a
webhook cannot do here.

*Send everything and let the receiving system filter.* It moves the interruption budget to a
Slack workspace's notification settings, where nobody can see it and nobody can argue with it.
