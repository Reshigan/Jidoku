# JIDOKA — FIRST PRINCIPLES
## The theory of the system, one level below the architecture
goNXT · jidoka (Latin root, live in Portuguese/Italian): *proof · test · dress rehearsal* — the three things this platform is.

---

## 01 — THE FAILURE PHYSICS OF ENTERPRISE PROGRAMMES

Strip away vendors, methodologies and politics, and every failed SAP programme fails the same way: **assertion
outruns evidence.** A status report asserts green while the build diverges; a design doc asserts agreement nobody
signed; a milestone asserts completion nobody can trace; a consultant asserts a statutory rule from memory; a
cutover asserts readiness rehearsed by no one. Each assertion is individually small. Compounded across eighteen
months and forty people, the gap between what is *said* and what is *jidokable* becomes the programme's real risk
register — invisible precisely because everything on paper still reads well.

Tooling to date attacks symptoms: better trackers, better templates, now better text generators. Generative AI on
its own makes the disease *worse* — it lowers the cost of fluent assertion to zero while doing nothing to the cost
of evidence. The deep move is to attack the physics: **make assertion structurally impossible and evidence
structurally cheap.** That is the entire platform, in one sentence.

## 02 — THE FIVE PRIMITIVES (a small calculus of trust)

Everything in JIDOKA reduces to five primitives; every feature is a composition of them.

1. **Signed Claim** — no value exists in the system without an owner's signature and a source location. Unsigned
   intent is not "draft"; it is unexecutable by construction.
2. **Provenance Chain** — every statement belongs to exactly one of three chains: about the *engagement* (traces
   to the knowledge graph), about the *product* (traces to metadata/documentation), about the *build* (traces to
   signed IR). A statement with no chain cannot be emitted. Fluency is never accepted as a fourth chain.
3. **Gate** — a predicate that blocks rather than warns: open decision points block plans, missing snapshots block
   apjidokals, SoD blocks self-review, write-locks block source systems. Warnings decay; gates do not.
4. **Ceremony** — the irreversible act as a formal ritual: named humans, rehearsed rollback, two signatures,
   ledger entry. The system treats a one-way door with the gravity a senior consultant feels in their stomach —
   encoded, so it survives staff turnover and 2am cutovers.
5. **Earned Status** — no state may be asserted, only derived: milestones from approved checkpoints, coverage from
   diffs, "best practice" from a counted delta budget, the consultant's competence from a graded exam, the
   platform's value from published curves. If a number cannot be earned, JIDOKA does not display it.

The hash-chained ledger is the accounting system of this calculus; the belief ledger extends it to cognition
itself — the platform's *beliefs* are as auditable as its actions.

## 03 — WHY THIS COMPOUNDS (the economic argument)

Evidence, once cheap, changes the economics of everything downstream. Verification stops being a phase and becomes
a property; rework — the true cost centre of implementations — is caught at twin-time instead of UAT-time;
auditors consume exports instead of consultant-weeks; and every engagement's scars (scrubbed to shapes) harden the
next one's gates. Human seniors stop being spent on keying and checking and are concentrated where they are
irreplaceable: judgment, decisions, the room. The platform does not replace the consultant; it removes every task
beneath their judgment — and *proves* the remainder. Margin, speed and trust compound from the same primitive:
proof made cheap — quality built in at the source, in the jidoka sense.

## 04 — THE NAME

**Jidoka (自働化)** — a pillar of the Toyota Production System: *automation with a human touch*. Toyota writes it
with a modified character: 働 — "movement" with the human radical 人 added. Automation, with the human built into
the word itself. The discipline it names: the machine runs autonomously and **stops itself the moment something is
wrong**, surfacing the defect and handing judgment to a person. Never pass a defect downstream; build quality in
at the source; give machines the ability to halt, and people the authority to decide.

That is this platform, sentence for sentence: autonomous execution, gates that halt rather than warn, defects
surfaced at twin-time not UAT-time, humans at every point of judgment, the andon board (our earned-status console)
showing the true state of the line at a glance. The name is not a metaphor borrowed for branding — it is the
fifty-year-old engineering discipline this system implements for enterprise configuration. Confirmed by Reshigan
(DP-N01 closed): the platform is **goNXT JIDOKA**. Pending before external use: trademark/domain search via
counsel and native-speaker mark review (katakana treatment ジドウカ, renderings, unintended readings).

## 05 — THE HOUSE LEXICON (TPS terms, used precisely)

| Term | In JIDOKA |
|---|---|
| Jidoka 自働化 | The platform: autonomous execution that stops itself and calls a human |
| Andon 行灯 | The status console: earned state visible at a glance; anyone can pull the cord (raise a halt) |
| Poka-yoke ポカヨケ | The gates: unsafe states made unselectable (SoD, write-locks, DP blocks, one-way ceremonies) |
| Kaizen 改善 | The learning loop: governed, eval-gated improvement with published curves |
| Genchi genbutsu 現地現物 | Extract-diff verification: go and see the actual state; never trust the report |
| Heijunka 平準化 | The run-planner: levelled, dependency-ordered flow instead of batch-and-panic |

*goNXT JIDOKA**.

*goNXT · What Comes Next is Built Here — and here, it is proven.*
