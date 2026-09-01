# What JIDOKA can honestly claim

A "world first" is a marketing phrase until it is broken into claims someone could check. This
document does that. Each claim below is either **verifiable in this repository** — a test proves
the gate holds, an ADR records the decision — or it is **not yet proven**, and says so. Do not
quote the first list without the second.

## Claims we believe are novel, and can demonstrate in code

Each of these is enforced by the kernel (stdlib-only, auditable with zero supply chain), covered
by tests, and recorded in an ADR. "Novel" means we know of no SAP configuration tool — SAP's own
or third-party — that ships the same governance shape. It does not mean nobody has ever thought
of it.

1. **Configuration drift is a blocking decision, not a report.** Every drift detector we know of
   produces a dashboard; some auto-remediate. Here a detected difference between signed intent and
   live state becomes a ledgered `DRIFT_DETECTED` entry plus a blocking decision point owned by the
   person who signed the record, with exactly two exits: re-apply the signed intent, or sign a new
   record adopting the observed state. Planning halts until a person answers. There is no
   reconcile, heal, or sync code path — a test asserts the absence. A system that drifts back into
   compliance keeps the question open, because a self-healing anomaly is an anomaly with better
   timing. (ADR-0013; `packages/jidoka-core/src/jidoka_core/drift.py`; `test_drift.py`.)

2. **Project documents and test plans are projections of signed state, not authored files.** The
   configuration rationale, cutover runbook and verification report are generated on read from
   signed IR, the decision register and the hash-chained ledger. There is no editor. A document
   that could disagree with the system cannot be produced. The verification "test plan" is the
   signed intent itself: settled fields are asserted, fields still behind an open decision are not
   tested, and objects never verified are listed as findings rather than silently omitted.
   (`packages/jidoka-compiler/src/jidoka_compiler/project.py`; `test_project.py`.)

3. **Number ranges are ledgered allocations.** Externally-coded SAP objects collide when two
   consultants pick the next "obvious" code. Here a range is registered once (overlaps refused),
   every allocation is a hash-chained ledger entry, a collision is refused at allocation time with
   the holder's name in the refusal, codes are never released for reuse, and an IR upload carrying
   an out-of-range code is refused before anything is kept. The ledger is the storage: the
   registry is rebuilt by replay. (ADR-0014; `packages/jidoka-core/src/jidoka_core/numbering.py`.)

4. **Unsigned intent is unexecutable by construction.** IR records without a signed source do not
   load; open decision points — whether from the IR or raised later, including by drift — hard-block
   planning through one gate; the agent is always builder and never approver; approval requires a
   different reviewer and a prior snapshot; live Tier-A writes require an explicitly armed target
   plus a ledger snapshot. These are the seven invariants in the root CLAUDE.md, each with tests.

## Claims we cannot yet make

- **"Proven on real engagements."** Zero production engagements have run on this platform. The
  Komatsu fixtures are fixtures.
- **"Writes to real SAP systems."** The OData connector exists and is tested against mocks; no
  live SuccessFactors or S/4HANA tenant has been written to from this codebase.
- **"Covers the SAP portfolio."** One reference adapter (SuccessFactors) is real; other products
  are tier-mapped but not implemented end to end.
- **"An LLM that fully understands SAP."** The knowledge subsystem is evidence-grounded and the
  scrubber gate works, but the corpus question (DP-K01 — entitlement to SAP documentation) is an
  open legal decision point and remains blocked until counsel answers it.
- **"World first" as a totality.** The four claims above are shapes we believe are new. The only
  honest form of the headline is: *the first SAP configuration platform we know of where drift,
  documents, tests and number ranges are all projections of one signed, hash-chained record — and
  where the machine can never approve its own work.*

*Last reviewed 2026-09-01. If a claim above stops being true, edit this file in the same PR.*
