# ADR-0026 — A twin predicts, and publishes how often it is right

Status: Accepted
Date: 2026-09-21
Relates to ADR-0012 (metadata is the primary source), ADR-0023 (assurance), ADR-0025 (controls).
Delivers E6.

## Context

`FIRST_PRINCIPLES` says rework is caught at twin-time rather than UAT-time. The twin was
`SchemaTwin`: a payload checked against `$metadata` for missing required fields, unknown fields
and orphan picklist references, and used by nothing outside its own test. That is real, it is
useful, and it is not what the sentence claims — it catches what the substrate would reject for
*shape*, and says nothing about the rules that reject most real configuration.

A repository that keeps a `CLAIMS.md` has two honest options with a gap like that: build the
thing, or soften the claim. This builds it, and the build is mostly about what a twin is allowed
to do with its own opinion.

## Decision

**Rules are evaluated from a declared, published subset.** A rule is `when` clauses and `then`
clauses over field comparisons — `eq`, `ne`, `in`, `not_in`, `required`, `empty`, `lte`, `gte`,
`matches`. `parse_rules` returns what it can evaluate and, separately, every rule it refuses with
the reason. It never raises: an export is somebody else's file, and the useful answer is which
parts of it this twin can honour. A twin that silently skipped the hard rules would report high
fidelity on the easy ones.

**Metadata comes from the system, never from an upload.** ADR-0012 already settled that a
system's own service definition outranks anything written about it. A twin calibrated against a
hand-supplied schema is measuring somebody's typing.

**The twin never blocks.** Not the plan, not the write, not the crew. A prediction is a model's
opinion, and a platform whose thesis is that assertion must be structurally impossible does not
let an opinion stop a signed, armed, snapshotted write that has passed every real gate. It
predicts, the prediction is ledgered as `TWIN_PREDICTED`, and a person decides.

**It earns its number in public.** `fidelity` is a projection over the chain, like assurance and
the controls: each prediction is paired with the next outcome the substrate recorded for that
record, and the rate is agreements over settled predictions. Below ten of them there is no rate at
all — `UNCALIBRATED` — because a percentage from a handful of comparisons is a number that gets
quoted rather than a measurement. Unsettled predictions are counted as unsettled rather than
dropped: a twin that graded itself only on the writes that happened would be grading itself on the
cases it found easy.

**The fidelity travels with the prediction.** Where the crew reports a predicted rejection, the
same sentence says whether the twin has earned any weight — *"this twin is uncalibrated (2 of 10
scored predictions), so it has earned no weight at all yet"*. A prediction quoted without its
track record is exactly the fluent assertion this platform exists to refuse.

## Consequences

- E6 is delivered in the shape the roadmap asked for — rule evaluation with a published fidelity
  metric — and the `FIRST_PRINCIPLES` sentence has code behind it for the first time.
- The twin will read `UNCALIBRATED` for a long time on any real engagement, and should. Ten
  settled predictions means ten writes that actually happened, which is the point: a twin nobody
  has tested against a substrate has no standing, however sophisticated its rules.
- Rules persist per engagement, as handed over, refused clauses and all. They are re-parsed on
  use rather than on load, so there is one parser and the refusal is part of the record.
- A rule export in SAP's own XML is still not readable. The subset is JIDOKA's shape, and
  converting SF's or S/4's export into it is work this ADR does not claim to have done.

## Alternatives rejected

*Let a calibrated twin block a write.* Tempting once the number is good, and wrong. The gates that
may stop a write are the ones that cannot be mistaken — a signature, a snapshot, an arming, an
open decision. A prediction that blocks is a prediction that has to be overridden, and an override
path is a gate with a hole in it.

*Parse SAP's rule XML directly.* A large, version-dependent guessing exercise whose failures would
be silent — a misparsed rule is a wrong prediction that still counts toward fidelity. A declared
subset that refuses what it cannot read is the honest first version.

*Report fidelity from the first prediction.* A twin that says "100% (1 of 1)" is worse than one
that says nothing, because somebody will put the first number in a steering pack.
