# ADR-0044 — The system's own change log against ours

Status: Accepted
Date: 2026-09-23
Relates to ADR-0019 (drift), ADR-0021 (assurance), ADR-0031 (the platform keeps its own record),
ADR-0043 (the verifier ships).

## Context

`CLAIMS.md` has named this since ADR-0031, under what the platform cannot measure: *"Work that
never reached a gate. A consultant who saw a refusal coming and did the change by hand in the SAP
GUI leaves nothing on this chain, and that is the most expensive failure this platform can have."*

Every projection here reads the ledger — assurance, the controls, drift, the accountability
record, the environment comparison. So a change made outside the platform is not under-reported.
It is invisible, and the numbers are confidently wrong rather than uncertain. An assurance figure
of 94% on a system somebody has been editing by hand is worse than no figure.

There is a second reason to do this now. SuccessFactors ships Change Audit — configuration and
data level, including role permission changes — free with every tenant, and SAP positions it for
detecting unexpected changes and identifying their source. That is a competitor to part of this
platform's pitch. It is also, read the other way, the missing input.

## Decision

**Consume the product's own audit trail rather than compete with it.** `POST .../reconcile` reads
the system's change log and pairs it against the ledger. The free feature becomes the thing that
closes the blind spot.

**Four outcomes, and the vocabulary carries the argument.** *matched* — both records agree.
*out_of_band* — in the system's log, not on our chain, on an object signed intent describes: the
finding this exists for. *unconfirmed* — on our chain, not in their log: reported as a question
and not an accusation, because it is usually a window or a scope mismatch. *out_of_scope* — a real
change to an object nobody designed, which is somebody else's business; counting it would make
every programme look breached by the rest of the tenant.

**The translation lives with the product.** Each adapter normalises its own log to
`{object, changed_by, ts, detail}`. SuccessFactors spells it one way, S/4's change documents
another, and the reconciliation should never learn either.

**An unreadable log is a refusal, never an empty result.** A reconciliation that found nothing and
one that could not look produce the same number and mean opposite things. An adapter with no log
says why, and the endpoint returns 409 with that sentence.

**An engagement nobody has reconciled says so.** The read endpoint reports *"every number here
assumes nothing was done outside the platform — which is an assumption, not a finding."* Silence
was previously indistinguishable from a clean result.

**Cost of silence 95**, above a half-landed write at 90. A partial write leaves a state nobody
designed and everybody can see; this is a change nobody knew about at all.

**The accountability record's stated limit was rewritten.** It claimed this was unmeasurable; it
is measurable now, where a product publishes a log and somebody ran the reconciliation. A stale
limit is worse than none, because it is the one that gets quoted.

## Consequences

- The out-of-band finding names a person, taken from the product's log. That is the product's
  claim about who changed it, not this platform's, and the wording says *the log does not name
  them* where it does not.
- The 10-minute pairing window is a judgement, published as one. A tenant's clock and a kernel's
  differ, and a product writes its log when a change commits rather than when the request arrived.
- A log row whose timestamp cannot be parsed is matched on the object alone. Calling a real change
  out-of-band because the tenant wrote a date in an unexpected format would be the worst kind of
  false positive.
- **The SuccessFactors entity name this adapter asks its fetcher for is unconfirmed against a live
  tenant**, like everything else in this codebase. The normalisation is tested against fixtures;
  the endpoint it reads from is the next thing a real tenant will correct.

## Alternatives rejected

*Watch harder — poll the system and diff continuously.* It answers a different question, costs a
read of the whole configuration on a schedule, and still cannot say *who*. The product's log knows
who, because the product did it.

*Treat every unmatched log row as out-of-band.* Then a programme touching twelve objects in a
tenant of thousands reports a breach every night, and the finding that matters is buried by the
rest of the business doing its job.

*Block on an out-of-band change.* Tempting, and wrong for the same reason drift's decision point
is owned by a person: the change may be entirely legitimate — an urgent production fix at 02:00 —
and the platform's job is to make sure it is not invisible, not to make it impossible.
