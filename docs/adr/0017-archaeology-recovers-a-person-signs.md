# ADR-0017 — Archaeology recovers; a person signs

Status: Accepted
Date: 2026-09-20
Relates to ADR-0001 (signed IR), ADR-0012 (metadata is the primary source), ADR-0013 (drift is a
decision), ADR-0015 (attestations are written by the act), invariants 1, 2 and 3.

## Context

Every surface built so far starts from signed intent: a workbook is compiled, a human signs it,
and the platform executes what the signature covers. That is the greenfield shape, and it answers
none of the market. Most SAP estates are running systems nobody designed on purpose — configured
over a decade by people who have left, where the design document either never existed or stopped
being true years ago. "Load your signed workbook" is not an answer to a tenant like that, because
the workbook is the thing that does not exist.

`jidoka-insight` has held the reversing code since the first commit — `reverse_ir` turns extracted
rows into IR-shaped drafts, `unexplained` names the ones with no recorded rationale — and nothing
imported it. Four working modules, no route, no screen, no path. A capability nothing can reach is
indistinguishable from one that was never written.

The reason it stayed unwired is the hard part, and it is worth stating plainly: reversing a live
system produces records that look exactly like configuration. If the platform treated them as
configuration, it would have invented the largest possible body of unsigned intent in one call —
precisely what invariant 1 exists to prevent — and every document and plan downstream would carry
it with the same authority as intent someone actually signed.

## Decision

**Archaeology recovers. It never signs.** `reverse_ir` emits `source.signed_by = ""` and
`date = ""`, so `ir.validate_record` refuses every draft (invariant 1) and no draft can reach a
plan. Drafts live in `Engagement.drafts`, which is not `Engagement.ir` and is never counted as it.

**Signing is a separate, named, human act.** `POST /insight/archaeology/sign` names the drafts to
sign, and the signature is `identity.subject` — the authenticated caller, per ADR-0015. There is
no signer field in the request and none in the console, because a platform that lets you type
somebody else's name into a signature field does not have signatures. Signing runs the records
through `load_ir` and the number-range gate exactly as an uploaded workbook does; it is the front
door with a different provenance written on it, not a side entrance into IR.

**Signing is the only connection to the rest of the platform.** Once signed, a recovered record is
ordinary IR: the planner sequences it, `config-rationale` prints it with the signature attached,
verification checks it against the live system it came from. Nothing in `routers/insight.py` plans,
documents or verifies anything. Archaeology is a door into the existing machine, not a second
machine beside it.

**Reading a system reads it.** Archaeology goes through the engagement's connector binding, so an
unbound system is a 409 rather than a read on an unauthorised path. The systems most worth reading
are SOURCE_LEGACY, which may never hold a write credential (invariant 3), so the binding used is
the read-only one from ADR-0016: the write half is absent, not refused.

**The debt index publishes its blind spots.** `debt.measure` counts only what the platform can
observe — unexplained drafts, open drift decision points — and returns `unmeasured` naming every
published weight it did not measure. A counter with no measurement behind it contributes zero and
says so, rather than being silently assumed to be zero. Debt rides on the backlog response rather
than a route of its own: a second endpoint returning a subset of the first is a second thing to
keep in step.

## Consequences

- A brownfield engagement has a first move that is not a lie: read the tenant, see the backlog,
  and answer objects one at a time. Each unexplained object is one question — why does this exist,
  and is it still wanted — with exactly three answers: sign it, decommission it, or record that
  nobody knows, which is itself the finding.
- `archaeology-backlog` is the first document that projects the *absence* of intent. Every other
  document projects what was signed; this one projects what was inherited and never examined.
  `jidoka-compiler` therefore depends on `jidoka-insight`, which is new and deliberate.
- The Repository protocol grows `save_drafts`/`load_drafts`. A backlog that vanished on a deploy
  would be work nobody does, so it is persisted — and `tests/test_repository.py`, which
  `repository.py` had claimed existed since the first commit, now exists and holds both
  implementations to one set of semantics.
- Re-reading a system replaces that system's drafts rather than appending to them. The live system
  is the authority on what it currently contains, and a stale draft is a lie about a real tenant.

## Alternatives rejected

*Sign drafts automatically and mark them low-confidence.* This is how every other reverse-engineering
tool works, and it is the failure this platform exists to refuse. A confidence score on an unsigned
value is still an unsigned value executing, and "low confidence" decays to "fine" by the second
sprint. Invariant 1 is not a confidence threshold.

*Adopt the live state as intent wholesale, then diff forward.* Identical in shape to the drift
behaviour ADR-0013 refused: it launders an unsigned change into the record. What a system does and
what somebody decided are different claims, and collapsing them is the whole disease.

*Let the agent write the rationale.* The agent can draft one — it is builder-capable — but the
rationale is the assertion that somebody understands why an object exists, and the party proposing
that understanding must not be the party ratifying it (ADR-0010's argument, applied to inheritance).
The field stays empty until a person fills it, and `unexplained` counts it until they do.
