# ADR-0023 — Assurance is counted from the chain, and says what it cannot count

Status: Accepted
Date: 2026-09-20
Relates to ADR-0002 (hash-chained ledger), ADR-0013/0019 (drift), ADR-0021 (the chase),
ADR-0022 (attestation), invariant 4. First half of E11's C6.

## Context

Every number this platform published was about work: steps planned, records loaded, objects
recovered, manual steps priced. None was about evidence, which is the number an auditor actually
arrives asking for — of everything this engagement says is done, how much can be demonstrated?

Until ADR-0022 the question could not be answered honestly, because the platform could not tell
the difference between a record it had read back from a live system and one nobody could read at
all. Now it can, and the three bases are on the chain in three different ledger actions. The
remaining risk is the familiar one: a single percentage is the most quotable artefact a platform
can emit, and a quotable number computed from a denominator nobody published is how "92% verified"
ends up on a steering pack meaning nothing in particular.

## Decision

**The classification is the product; the percentage is derived from it.** `jidoka_core.assurance`
reads the ledger and files every signed record under what its claim to being done rests on:

| basis | ledger verdict | what it is |
|---|---|---|
| checked | `VERIFIED` | this platform read the live system and found the signed value |
| disagrees | `DRIFT_DETECTED` | read, and the system says something else |
| attested | `ATTESTED` | a named person's word; no read path exists |
| unevidenced | `UNCONFIRMABLE` | no read path and no attestation |
| outstanding | `AWAITING_A_PERSON` | handed over, not done yet |
| unbuilt | `NOT_APPLIED` | nothing written |
| unexamined | *(nothing)* | no verification has ever looked at it |

Nothing is inferred from the absence of an entry except `unexamined`, which is the honest name for
that absence rather than a guess about a live system nobody has read.

**The denominator is published with the number.** `proven = checked / (checked + disagrees +
attested + unevidenced)` — every record something claims is done, over the subset the platform
read back itself. The three bases left out are named in the same breath, because they assert no
completion and counting them would move the score for reasons that have nothing to do with
evidence, in whichever direction the folding happened to go.

**An attestation never counts as proof.** It sits in the denominator and not the numerator, which
is the entire reason this number is worth printing: a platform that added a person's word to its
own readings would produce exactly the reassuring total that made the question worth asking.

**Nothing claimed means no score, not zero.** `fraction` is null on an empty set. A 0% on a
fresh engagement reads as a failure when the true statement is "nothing has been claimed yet".

## Consequences

- The Verification Report leads with it, and its "never verified" list had to be widened to every
  verdict — a record the platform found unreadable *has* been looked at, and listing it as never
  verified contradicted the table three paragraphs above.
- `IRRecord.key` was written twice, and the copy in the projection layer took a dict and quietly
  returned nothing, so the first assurance count read every record as unexamined. There is one
  `record_key` now, in `ir.py`, taking either shape.
- `jidoka_os.crew` imports the verdict vocabulary from core rather than keeping its own copy. The
  package has always depended on jidoka-core and imported nothing from it; this is the first thing
  worth sharing, and a second copy of the ledger's own vocabulary was a second thing to keep in step.
- The number will look bad on a real engagement, and should. A first pass over a brownfield tenant
  with a dozen Provisioning-only objects will read well under half proven. That is the estate
  being what it is, and a platform whose assurance metric flatters it is not measuring assurance.

## Alternatives rejected

*One "verified" percentage over all records.* The obvious version, and it moves whenever somebody
loads more intent — a number that improves when you delete unbuilt records and worsens when you
plan more work is not measuring evidence.

*Weight the bases and emit a score.* The debt index does this and publishes its weights, which is
fine for a debt heuristic. Assurance is a claim about proof, and a weighted blend of "we read it"
and "somebody says so" is precisely the blurring this exists to prevent.

*Count an attestation as proof after a reviewer countersigns it.* Two people's word is still
nobody having read the system. Countersigning belongs to approval, which the ledger already gates
with reviewer != builder, and it answers a different question.
