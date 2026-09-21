# ADR-0027 — The night shift speaks on a budget

Status: Accepted
Date: 2026-09-21
Relates to ADR-0018 (the crew), ADR-0021 (the chase), ADR-0025 (controls), ADR-0026 (the twin).
Delivers the first two items of E12, from docs/JIDOKA_TEAM_MEMBER_MODEL.md M1–M3.

## Context

`scheduler.py` has held a shift clock, an interruption budget and a cost-of-silence queue since
the first commit, and nothing ever scheduled anything. The same shape as the kernel's handler
table and `jidoka-insight`: a mechanism with no caller is a diagram.

The team-member model is specific about why it exists. A tool has sessions; a colleague has a
working day, does the work that needs no person overnight, and opens the morning with a handover
rather than a dashboard. And a colleague with initiative but no restraint is spam — so the
proactive voice is metered, ranked by what it costs the programme if something goes unsaid until
morning.

## Decision

**The night runs what already exists.** Verification, the controls, the twin's fidelity, the
chain, the armings. The night shift is not a new capability; it is the decision to run them while
nobody is watching and to arrive in the morning with the work started.

**Every finding carries what silence costs.** A published table, from a broken chain at 100 down
to a twin miss at 10, because a budget whose ranking cannot be argued with is a feeling. Above 55,
a finding is worth waking somebody for. Below it, the morning is soon enough.

**The budget is hard and an unspent budget stays unspent.** Three interruptions by default, spent
on cost rather than on order of discovery — a chain break found at 04:00 outranks a control that
failed at 22:00. A night that finds four urgent things interrupts three times and says in the
handover that it held one back. It never drops the fourth.

**The handover is first person, in three parts.** *What I did · what I found · what I need from
you today.* First person because the third person turns it into a status report and nobody reads
those. Three parts because the last one is the only part somebody has to act on. It ends by saying
how often it woke somebody and why — including "I did not wake anybody. Nothing overnight was
worth it", which is the sentence that makes the other ones credible.

**It is on the chain.** A `HANDOVER` entry records the findings and the interruptions spent, so
the morning can prove the night happened rather than take its word for it.

## Consequences

- The platform now has a voice that is not a reply. That is a real change in posture and the
  budget is the only thing keeping it from being a nuisance — the threshold and the cost table are
  published so they can be tuned in the open rather than felt.
- A half-landed write that was put back is not raised again: the rollback's own ledger entry
  settles it (ADR-0024). The night reports what nobody has dealt with, not everything that ever
  went wrong.
- `Finding` has no notion of *who* beyond a string. M4 — routing to the cheapest sufficient
  authority, respecting working hours, not pinging Maputo at 06:00 on a Saturday — needs person
  profiles, which do not exist. The handover names a role and stops there, honestly.
- Nothing here schedules itself. Running the night is still a call somebody or something makes;
  a cron, a queue consumer or a Cloudflare trigger belongs to deployment, not to this.

## Alternatives rejected

*Interrupt on everything and let people filter.* What every monitoring tool does, and the reason
nobody reads them. The budget is the product.

*Rank by severity taxonomy.* Severity is a property of a thing; cost of silence is a property of
the delay, which is the actual decision being made at 04:00. They come apart: a drifted record is
severe and can wait until 08:00; a lapsed arming is trivial and blocks a cutover window.

*Compose the handover with the K5 consultant.* It would read better and it would be a model's
account of a night it did not work. The handover is assembled from the findings themselves, so
every sentence in it is a row on the chain.
