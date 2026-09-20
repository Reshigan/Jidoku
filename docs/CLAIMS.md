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

4. **An unattended crew configures the system and structurally cannot sign off on it.** Five
   agents with opposed objectives run an engagement: sequence, snapshot, write every Tier-A step
   an approver has armed, carry an ABAP change along its declared route until it lands in
   production, emit the artefacts a person must do by hand, raise the statutory questions nobody
   may guess, object to their own output, price the remainder and verify. Every effect goes
   through a capability-checked syscall bound to the same executor the console's buttons use, so
   the crew has the operator's route to a customer's system and less authority than the operator:
   no syscall arms anything, the executor refuses an arming whose holder is the actor spending it,
   and APPROVE exists in no ring an agent can occupy. An arming is a window with a stated expiry
   rather than a standing authority; a Tier B/C artefact handed to a person is chased from the
   live system until a re-read finds the work done; and where the product publishes no read path
   at all, the adapter says so and the record is a named person's attestation — never counted as
   a verification — rather than a chase with no end. A run that configures a whole landscape ends
   unapproved, waiting on a reviewer who did not build it. (ADR-0018, ADR-0020, ADR-0021;
   `packages/jidoka-os/src/jidoka_os/crew.py`; `test_crew.py`, `test_run_api.py`.)

5. **The platform publishes how much of its own work it can prove.** Every signed record is filed
   by what its claim to being done rests on — read back from the live system, a named person's
   word, nothing at all, or not claimed yet — and the headline is `checked / (checked + disagrees
   + attested + unevidenced)`, with the denominator and the three excluded bases printed beside
   it. An attestation sits in the denominator and never the numerator. We know of no configuration
   tool that reports its own assurance as a fraction it can be argued with about. (ADR-0023;
   `packages/jidoka-core/src/jidoka_core/assurance.py`; `test_assurance.py`.)

6. **Unsigned intent is unexecutable by construction.** IR records without a signed source do not
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
- **"The crew replaces a consulting team."** It does a team's *mechanical* pass: sequencing,
  writing, transporting, artefact production, statutory challenge, objection, pricing and
  verification — deterministically, and only ever against a mock SAP double, because no live
  tenant has been written to from this codebase at all. It brings no judgement of its own: the
  statutory sentinel matches field names against a published word list, it does not understand
  South African leave law. Read the claim as "an unattended pass that configures what an approver
  has armed and stops at every human judgement", which is what the tests prove.
- **"An LLM that fully understands SAP."** The knowledge subsystem is evidence-grounded and the
  scrubber gate works, but the corpus question (DP-K01 — entitlement to SAP documentation) is an
  open legal decision point and remains blocked until counsel answers it.
- **"World first" as a totality.** The six claims above are shapes we believe are new. The only
  honest form of the headline is: *the first SAP configuration platform we know of where drift,
  documents, tests and number ranges are all projections of one signed, hash-chained record — and
  where the machine can never approve its own work.*

*Last reviewed 2026-09-20. If a claim above stops being true, edit this file in the same PR.*
