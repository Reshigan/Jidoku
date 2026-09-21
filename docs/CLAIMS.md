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

6. **Controls are predicates over the whole population, not prose with a sample attached.** Six
   controls — prior snapshot, no self-approval, armed by a second person, two approvers on a
   one-way decision, transports that reached production, no write to a write-locked system — run
   over every row of the engagement's ledger on demand, enumerate their violations in full rather
   than counting them, and distinguish "nothing to test" from "passed". The population is complete
   because every act that touched a customer's system is on the chain or did not happen through
   this platform. (ADR-0025; `packages/jidoka-core/src/jidoka_core/controls.py`; `test_controls.py`.)

7. **The twin publishes how often it is right, and is never allowed to act on it.** Rules are
   evaluated from a declared subset that refuses what it cannot read rather than approximating it;
   metadata comes from the system itself; every prediction is ledgered and paired afterwards with
   what the substrate actually did. Below ten settled predictions there is no fidelity rate at
   all, and where a prediction is quoted the same sentence says how much weight it has earned. A
   prediction never blocks a write. (ADR-0026; `packages/jidoka-core/src/jidoka_core/twin.py`;
   `test_twin.py`.)

8. **Unsigned intent is unexecutable by construction.** IR records without a signed source do not
   load; open decision points — whether from the IR or raised later, including by drift — hard-block
   planning through one gate; the agent is always builder and never approver; approval requires a
   different reviewer and a prior snapshot; live Tier-A writes require an explicitly armed target
   plus a ledger snapshot. These are the seven invariants in the root CLAUDE.md, each with tests.

9. **The platform records what it refused, and reports how often its own gates were friction.**
   Every 403, 409 and 422 is a `REFUSED` entry on the same hash-chained ledger as the work it
   declined, named by route template so the same gate across eleven engagements is one gate; when
   the same person later gets past it, that is a `CLEARED` entry at the same seam. From those two,
   `GET .../accountability` reports each gate as *cleared fast every time* — friction wearing a
   governance costume — or *never cleared* — stopping something real. Nothing is scored, because a
   number would be quoted; and what the record cannot see is printed beside it, starting with the
   consultant who saw a refusal coming and made the change by hand in the SAP GUI. We know of no
   compliance or configuration tool that publishes its own false-friction rate. ADR-0031.

10. **The platform reports its own silence.** A night shift writes a handover on every run, a
    failure when one raises, and nothing when the clock stops — so `clock()` reads the absence off
    the chain and the console says *"no night has been worked in 21 days"* against a cadence the
    engagement declared. Every way a scheduled job dies is invisible from inside the run that did
    not happen; at the edge, `GET /__edge` answers whether the deployment is wired up in booleans,
    never values. ADR-0030.

11. **One roll-up, no second opinion.** `GET /portfolio` shows every engagement worst-first with
    the same projections each engagement's own screen runs — no stored aggregate, no portfolio
    average, and one sentence per row saying what needs a person rather than a colour they have to
    decode. ADR-0032.

12. **Two implementations of the chain, one spec.** The Durable Object port of the ledger and the
    Python kernel are both held to the same fixture — the same operations, the same hashes, the
    same refusal messages, byte for byte — and CI runs both. The drift this prevents is not
    somebody weakening a rule; it is `JSON.stringify` putting no space after a comma where
    `json.dumps` does, producing a chain that verifies against itself and fails against every
    chain the kernel ever wrote. ADR-0037.

## Claims we cannot yet make

- **"Proven on real engagements."** Zero production engagements have run on this platform. The
  Komatsu fixtures are fixtures.
- **"Writes to real SAP systems."** The OData connector exists and is tested against mocks; no
  live SuccessFactors or S/4HANA tenant has been written to from this codebase.
- **"Covers the SAP portfolio."** Three adapters exist — SuccessFactors (the reference, with a
  live OData client), S/4HANA (OData plus transport-aware completion) and BTP (Terraform-declared,
  Tier B by design). None has been pointed at a live tenant from this codebase, and BTP has no
  live connector at all: `_live` refuses it by name rather than shipping an untested write path
  into a customer's control plane.
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
- **"We measure whether our gates are correct."** The refusal record counts how fast each gate was
  cleared, which is a proxy for friction and not a verdict: a gate cleared in a minute may have
  caught a real mistake a minute before it landed. Nothing on the chain distinguishes the two.
- **"We measure harm avoided."** A change that was never made because the platform blocked it
  cannot be compared against the world where it was made. Any number claiming otherwise is
  invented, and none is published.
- **"The kernel runs at the edge."** The ledger does, and is proven to. The registry's write-lock,
  the executor's arming and snapshot gates and the decision engine's STATUTORY and ONE_WAY rules
  are not ported, and `wrangler.phase2.toml` is not deployed.
- **"World first" as a totality.** The twelve claims above are shapes we believe are new. The only
  honest form of the headline is: *the first SAP configuration platform we know of where drift,
  documents, tests and number ranges are all projections of one signed, hash-chained record — and
  where the machine can never approve its own work.*

*Last reviewed 2026-09-21. If a claim above stops being true, edit this file in the same PR.*
