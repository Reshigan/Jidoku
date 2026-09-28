# ADR-0022 — What cannot be read back is attested, not chased

Status: Accepted
Date: 2026-09-20
Relates to ADR-0003 (native substrates only), ADR-0015 (attestations are written by the act),
ADR-0021 (a handoff is a chase), invariants 1 and 4.

## Context

ADR-0003 is what makes Tier B and Tier C honest rather than an excuse: the platform declares that
a product publishes no write path for an object, emits an instruction sheet, a person does the
work, and JIDOKA confirms it by extract-diff. "Verification is automated even where writes are
manual" is one of the platform's load-bearing claims, and it rests entirely on a read path
existing.

For a good number of objects it does not. An SF Provisioning switch, a succession data model, an
MDF object definition, an S/4 IMG table — the product keeps them behind a UI and publishes
nothing that reads them back. Nothing in the tier map said so. ADR-0021 then made it worse in the
most helpful possible way: a handed-off record absent from the live system became a chase, so the
platform began asking, every run, forever, for confirmation of work it could never see. A chase
with no end is not diligence. It is a queue that trains people to ignore the queue.

Underneath it was a quieter problem. The tier map declared what a product could be *written*
through and said nothing about what could be *read*, so "Tier C" meant two very different things
— an object a person changes and JIDOKA checks, and one a person changes and nobody ever checks —
with no way to tell them apart.

## Decision

**An adapter declares what it cannot read back.** `Adapter.unverifiable()` returns entity → the
reason, and `verifiable(entity)` follows from it. Both adapters derive theirs from the one map
that names a read path rather than keeping a second list: SF from `ENTITY_SETS | READ_ONLY_SETS`,
S/4 from `SERVICES`. A second list of the same fact is a second thing to keep in step, and an
entity becomes confirmable the day a service is added for it, with no edit anywhere else.

`READ_ONLY_SETS` is new and is the point of the distinction: SF publishes readable entity sets for
objects nothing may write — a time account detail, a holiday, a picklist option. Those are Tier B
or C *and* confirmable, which is exactly the ADR-0003 bargain working. Keeping them out of
`ENTITY_SETS` matters, because a readable set that leaked into the write map would become a
live-write bug.

**`audit_tier_map` separates a lie from a limit.** A Tier-A entity with no write target is a
defect — the adapter claims a write path it cannot name, and an armed step against it fails at the
substrate with a live target already armed. A Tier-B/C entity with no read path is not a defect;
it is the product being what it is, and it has to be visible. Each adapter's own test suite
asserts it tells the truth about both.

**Verification reads nothing it cannot read.** Where the adapter publishes no path, the platform
does not call extract and does not file the failure under "could not be read" — that reads like a
transient fault when it is a permanent property of the substrate. The record is `UNCONFIRMABLE`,
on the ledger, with the reason.

**What is owed there is a person's word.** `POST /execution/attest` records that a named person
made the change. It is written by the act under the caller's own identity (ADR-0015), `ATTESTED`
is a reserved ledger action so it cannot be posted as a free-form row, and the entry carries the
hash of the intent it covers — when the signed intent moves, the attestation retires rather than
silently inheriting the new version. Attesting to an object the platform *can* read is refused
with a 409: there, the live system answers, and a person's word substituting for a machine check
is the disease this platform exists to treat.

**An attestation is never counted as a verification.** It is a separate status, a separate column
and a separate sentence — "attested, not checked". The platform has not seen the system, and a
report that blurred the two would be worth less than one that admitted the gap.

**None of this blocks the plan.** A missing read path is a fact about a product, not a question
about a configuration. Blocking would stop every engagement that touches a Provisioning switch,
and invariant 2 is for values nobody may guess.

## Consequences

- SF declares 35 of its 87 mapped entities unreadable, S/4 19 of 28. Those numbers are the honest
  shape of the SAP surface and should be quoted as such rather than quietly improved.
- The Komatsu fixture's `DATA_MODEL_XML` moved out of "awaiting a person" and into "no read path".
  Two tests changed, and one of them had been seeding a mock row for an object SF does not publish
  as an entity set — a fixture proving something the real product cannot do.
- The Crew screen now carries five verification counters: matched, unexplained, not built,
  no read path, and attested. Five absences with five meanings; folding any two together is what
  made the Verify screen misleading in the first place.
- A tier map is now a claim about reading as well as writing, and a new adapter has to answer both.
  That is more work per adapter and it is the work: an adapter that cannot say what it can read
  cannot honour ADR-0003.

## Alternatives rejected

*Refuse to tier-map an object with no read path.* The first instinct, and wrong. A Provisioning
switch is real configuration that a real consultant changes on a real programme; refusing to model
it does not make anything safer, it just moves the object off the ledger and out of the documents
into somebody's spreadsheet.

*Let the chase continue and rely on people ignoring it.* This is what the code did. A queue that
is always wrong is a queue nobody reads, and it would have degraded the chases that are real.

*Accept an attestation for anything, readable or not.* It makes the API simpler and lets a claim
mask a machine-checkable failure. The 409 is the feature.

*Have the crew attest.* Ring 2 has no capability for it and never should. An attestation is a
person saying they did something; a machine saying a person did something is not evidence, it is
a forgery with good intentions.
