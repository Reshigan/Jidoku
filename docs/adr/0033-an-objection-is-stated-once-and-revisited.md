# ADR-0033 — An objection is stated once, overridden by a name, and revisited where it lands

Status: Accepted
Date: 2026-09-21
Relates to ADR-0018 (the crew), ADR-0027 (the night shift), ADR-0031 (the platform keeps its own
record). Delivers the last E12 item, from M6 of docs/JIDOKA_TEAM_MEMBER_MODEL.md.

## Context

M6 is one paragraph and every clause in it is a constraint:

> When a plan conflicts with a codex rule, JIDOKA states the objection **once**, in plain terms,
> with the consequence and its recommendation — then defers, records the override with the
> decider's name, and **revisits it at the point where the consequence lands**. Not to be right;
> because the loop closing is what makes the next objection worth hearing.

The crew's auditor has objected since ADR-0018 — from a ring that cannot write, which is the
point — onto an in-memory bus. The run reported the objections and dropped them. So the platform
disagreed and nothing recorded it, nobody could be named as having overruled it, and nothing ever
came back to see what happened. What existed was the easy half: having a position. The half that
costs something, and the only half that makes the next objection worth hearing, was missing.

## Decision

**Identity is what it is about and what it found.** `objection_id` is derived from the pair, so
*state it once* is enforceable rather than remembered. Raising the same objection again appends to
the chain and increments `restated`; it does not produce a second objection and the reader is not
told twice. A tool that repeats itself is a tool people configure to be quiet, and then the one
objection that mattered is quiet too.

**The consequence and the recommendation are required at the point of raising.** A finding with
neither is a complaint, and a consequence invented later to justify an objection is not a
prediction. The crew's auditor now states all three for each of its five findings.

**Grounds are a closed set** — `unevidenced`, `unsafe`, `uneconomic`. A platform that can object to
anything objects to everything.

**Nothing blocks.** An objection is not a gate. The gates are the seven invariants and they
refuse; this is the platform disagreeing with a decision it has no standing to prevent, and
dressing that as a gate would be the platform voting. The console panel sits a rank below the
decision points for the same reason.

**The override carries a person's name and their reason,** and takes `approve` — overruling the
platform's stated position is a decision, and the platform is never the one who makes it
(invariant 7). An override nobody signed is the platform being overruled by the weather.

**The revisit happens at a phase, not on a timer.** `revisit_at` defaults to `HYPERCARE`, where a
configuration decision stops being an opinion and starts being somebody's morning. Nothing is due
before then: a revisit early is a platform asking to be told it was right. The night shift is
where the loop closes — `objection_due` ranks at 25, above a stale attestation and below a live
drift, which is what it is worth.

**What the revisit reports is what the chain says, never who was right.** "The objection was
right" is a claim about a world where the override did not happen, and nothing here can see that
world. So it reports the ledger's own words about that record since — drifted, verified, rolled
back, still attested — and where the ledger recorded nothing it says that explicitly rather than
reading silence as agreement.

**State is a projection.** Open, overridden, withdrawn, revisited are all read back from entries.
A restart cannot lose an objection and no second copy can disagree with the chain.

## Consequences

- The auditor's five findings now carry consequences and recommendations written out in full,
  which makes them longer and makes them arguable. Both are improvements.
- Withdrawal exists: the platform concedes on the chain, beside the objection, so a reader sees
  both. Without it the only exits were being overruled or being right.
- An engagement that never reaches HYPERCARE never revisits anything. That is correct — the
  consequence has not landed — and it means a long-running BUILD can accumulate set-aside
  objections that nothing chases. The night shift will chase them the day the phase advances, and
  nothing chases them before.
- `what_happened` reads every entry for the record, so an objection about a step with a busy
  history reports several outcomes at once. That is the chain being honest rather than the
  platform picking the one that suits it.

## Alternatives rejected

*Block on an unresolved objection.* It would make the platform's opinion a gate, and the whole
design rests on gates being the seven invariants and nothing else. A tool that can stop work
because it disagrees is a tool that gets its objections disabled.

*Revisit on a timer.* Thirty days after an override is a date, not a consequence. The point M6
makes is that the loop closes where the thing predicted becomes observable.

*Score the platform's objections — how often it was right.* The counterfactual is unavailable, and
a score would turn the objector into something that optimises for being provably right rather than
for being useful. It would also be quoted.
