# ADR-0031 — The platform keeps its own record, including where it was wrong

Status: Accepted
Date: 2026-09-21
Relates to ADR-0021 (assurance), ADR-0024 (the twin reports its own fidelity), ADR-0030 (a night
that did not run reports itself). Delivers E12's self-accountability item.

## Context

The gates are the product. A plan blocked on an open statutory decision, an approval refused
because the reviewer was the builder, a live write refused because nothing was armed — this is
what JIDOKA is bought for, and every one of them returned a 403 or a 409, was read once by the
operator, and was gone. Nothing recorded it.

So the platform could not answer the question a customer eventually asks of any governance tool:
**are these gates right, or are they friction?** It could not even answer the weaker version — how
often did we refuse anything at all? A ledger that records every action the platform took and
nothing it declined to take is a record of half the product, and the missing half is the half it
was bought for.

The same absence, one level up: the platform publishes assurance, control results and twin
fidelity, and every one of them is about the engagement. Nothing was about JIDOKA. A governance
tool that publishes only its successes is asking to be trusted on its own account, which is the
thing it exists to stop anybody else doing.

## Decision

**A refusal is a ledger entry.** `REFUSED`, written at one seam — a single exception handler over
every 403, 409 and 422 — rather than in each router, because a gate that only sometimes records
itself is worse than one that never does: the gaps read as gates that never fired. 401 is
deliberately absent. An unauthenticated call is not a gate firing, it is a request that never
reached one, and counting them would bury the refusals that mean something.

**The gate is named by route template, never by URL.** `POST /engagements/{eid}/execution/execute`,
so the same gate on eleven engagements is one gate. Named by URL, each id would be its own row and
a pattern across a portfolio would be invisible — which is the only scale at which this question
gets interesting.

**What is recorded is the route, the status, the person and the platform's own words.** Never the
request body: a body can carry a credential, and a refusal is not a reason to persist one.

**A clearing is a ledger entry too.** `CLEARED`, written at the same seam when somebody who was
refused at a gate later gets past it. Without it the record would say how often gates fired and
nothing about whether they held, and "how often we said no" on its own is a vanity number. It is
written only when there is an outstanding refusal to clear, which is what keeps a record of every
gate from becoming a record of every request.

**"Cleared" is the word, not "overturned".** Nothing here knows whether a refusal was correct.
Somebody else succeeding where you were refused is separation of duties working, not your refusal
being overturned, so a clearing requires the same person at the same gate.

**Nothing is scored.** A single number would be quoted, and the questions are the product: did my
gates stop work that was fine, was my twin right, what did I get wrong, and what can I not
measure. `FRICTION_WITHIN_HOURS = 1.0` is published as a judgement about what friction means
rather than presented as a measurement.

**What it cannot see is printed beside the numbers.** Work that never reached a gate — a
consultant who saw a refusal coming and made the change by hand in the SAP GUI — leaves nothing on
this chain and is the most expensive failure the platform can have. Harm avoided cannot be
measured against a world where the change was made. Both are stated where the numbers are, because
the gap between what a metric covers and what a reader assumes it covers is where every dishonest
dashboard lives.

## Consequences

- The ledger grows by one entry per refusal. That is the point, and it is small: a refusal is rare
  compared to the work around it, and a platform refusing often enough for this to matter has
  found something worth knowing.
- A gate cleared inside the hour every time is now visible as such, and somebody will eventually
  argue that it should be removed. That argument is the feature. It was previously unavailable,
  and gates were kept or dropped on instinct.
- `GET /engagements/{eid}/accountability` is gated on `read`, not on an audit role. Somebody
  deciding whether to trust this platform should not need a privileged role to see how often it
  has been wrong.
- Drift found on a record the platform had already called verified is counted apart from drift in
  general. The first is the platform being wrong with confidence; the second is the system
  changing under a correct reading, and adding them would flatter the first by hiding it in the
  second.
- The recording can fail without changing an answer: a ledger that is down loses the record of a
  refusal and never turns a 403 into a 500. The operator's refusal message is the part that cannot
  fail.

## Alternatives rejected

*Record refusals in each router.* Nineteen places to remember, and the first one forgotten reads
as a gate that never fires. A governance record with silent gaps is worse than none.

*Score the platform.* A number would be quoted, compared between vendors, and optimised. The four
questions cannot be optimised without actually improving, which is the only reason to publish
them.

*Call a fast clearing a false positive.* A gate cleared in a minute may have caught a real mistake
a minute before it landed. Nothing on the chain distinguishes the two, and inventing the verdict
would be exactly the kind of claim this platform refuses to let anybody else make.
