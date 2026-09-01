# JIDOKA — ADVANCED CONCEPTS v1.0
## Seven sophistications that raise the platform from disciplined automation to formal engineering
Status per concept: **[BUILDABLE NOW]** / **[RESEARCH]** — stated honestly; sophistication that cannot ship is a
slide, not a product.

---

## C1 · CONFIGURATION AS A FORMAL SYSTEM — TYPED IR WITH REFINEMENT TYPES **[BUILDABLE NOW]**

Today IR is validated (schema, refs). Sophistication is IR that is **typed with statutory and referential
refinements**, so whole classes of defect become *unrepresentable* rather than *detected*:

```
TimeType(country=ZAF) : LeaveType
  where entitlement ≤ statutory_max(ZAF, signed_source)     -- refinement carries its authority
    and currency = legal_entity.currency                     -- dependent on another object's value
    and cycle_context ≠ ⊥                                    -- R-107 encoded in the type
```

Consequences: a plan is *type-checked*, not merely ordered; illegal states cannot be written because they cannot be
constructed; and the type-checker's rejection message doubles as the auditor's control narrative. This is
poka-yoke pushed into the type system — the deepest version of "unsafe states unselectable."

## C2 · SEQUENCING AS CONSTRAINT SATISFACTION, NOT TOPOLOGICAL SORT **[BUILDABLE NOW]**

Topological sort answers *what order is legal*. A senior consultant answers a harder question: *what order is
optimal given approver availability, statutory blocks, transport windows, freeze periods, country sign-off
latency, and consultant skill coverage*. That is a scheduling problem over a constraint graph with resources —
solvable with a CP-SAT solver over the IR graph, minimising expected time-to-earned-milestone subject to:
one-way doors ordered by required-by date, reversible decisions deferred to cheapest-last (R-604), approver
capacity as a renewable resource (the real bottleneck at scale), and country sign-off latency as per-country lag.
Output: a plan that is provably feasible and explicitly optimal against a stated objective — plus the shadow
prices, which tell the programme director *which constraint to buy their way out of*. No SAP tool computes that.

## C3 · PROBABILISTIC PROGRAMME FORECASTING — REPLACING THE GREEN/AMBER/RED LIE **[BUILDABLE NOW]**

Status colours are assertion; JIDOKA already earns status from checkpoints. The sophistication is a **Bayesian
forecast over the plan graph**: each task carries a duration distribution updated from this engagement's own
actuals (and the scrubbed cross-engagement prior), each open DP a resolution-latency distribution fitted to that
client's observed decision speed, each defect class an escape probability from the twin's calibration record.
Monte-Carlo the graph nightly → **P(go-live ≤ 1 Dec) with a credible interval, and a ranked list of which single
intervention moves the distribution most.** Steering stops debating colours and starts buying probability. The
honest corollary, which is the point: when the number is 0.31, the platform says 0.31.

## C4 · THE CAUSAL LAYER — WHY THE DEFECT HAPPENED, NOT JUST THAT IT DID **[RESEARCH]**

Reject logs give correlation. A senior gives causation: *"this rejected because the FO effective date postdates the
migrated employment, which happened because the FO load used build-day defaults."* Build a causal graph over
config decisions → defects, fitted from engagement history (decisions and outcomes are both fully observed in the
ledger — a rare luxury). Then two capabilities no defect tracker has: **counterfactual query** ("would this defect
class have occurred had we chosen option B?") and **intervention ranking** (which upstream decision, changed now,
eliminates the most downstream defect mass). The ledger's completeness is what makes this tractable at all.

## C5 · MULTI-AGENT ADVERSARIAL DESIGN — SEPARATION OF COGNITIVE POWERS **[BUILDABLE NOW]**

One agent with one objective self-justifies. Sophistication is an economy of agents with *opposed* objectives and
no shared memory, arbitrated by a human:
- **Architect** — maximise fit-to-standard within constraints.
- **Auditor** — maximise findings: unproven claims, missing evidence, control gaps. Rewarded for what it breaks.
- **Statutory sentinel** — single-purpose: detect any value that should be a signed client source. Adversarial to
  the Architect's convenience by construction.
- **Operator** — minimise execution risk: sequencing, rollback viability, cutover feasibility.
- **Economist** — price everything: delta-pool cost, cost-of-delay per open DP, lifetime cost of each custom field.
Disagreement is the product: a design that survives four hostile reviewers arrives at the human with its
objections already documented — which is precisely what a J-SOX design review is supposed to produce and rarely does.

## C6 · THE EVIDENCE COMPILER — CONTROLS AS EXECUTABLE SPECIFICATIONS **[BUILDABLE NOW]**

Today controls are documents and evidence is assembled toward them. Invert it: write each control as an
**executable predicate over the ledger and system state**, e.g.

```
CONTROL C-PAY-01 (bank detail dual approval):
  ∀ change ∈ PaymentInformation(period) :
      ∃ approval ∈ ledger where approval.task = change.task
        ∧ approval.actor ≠ change.actor ∧ approval.ts ≥ change.ts
  ⇒ evidence: (change, approval) pairs; violations: enumerated, not sampled
```

Then the control *tests itself continuously* over the whole population — no sampling, no audit season, and a
failure is an alert on the Andon board the day it happens rather than a finding six months later. Sophistication
here is not more automation; it is changing controls from prose to logic, which lets the same artefact serve
design, testing, monitoring and the audit file. Complete-population assurance is a claim external auditors cannot
currently make about any SAP programme.

## C7 · MECHANISM DESIGN FOR THE HUMAN LAYER — THE REAL FRONTIER **[RESEARCH]**

Once configuration is cheap and verified, the binding constraint is human decision throughput (R-701, R-802).
The sophisticated move is to treat the programme as a **mechanism to be designed**, not a process to be managed:
route each DP to the *cheapest sufficient authority* (not always the most senior); bundle decisions to minimise
context-switching cost per approver; price delay explicitly so a client trading a week of decision latency sees
its cost in the same units as scope; and expose approver load so the bottleneck is visible before it bites.
This is where the remaining order-of-magnitude sits — not in writing config faster, but in making a large
organisation decide faster without deciding worse.

---

## WHAT MAKES THIS COHERENT RATHER THAN A FEATURE PILE
All seven serve one thesis (First Principles §01): make assertion impossible and evidence cheap. C1 moves it into
types, C2 into optimisation, C3 into probability, C4 into causality, C5 into institutional design, C6 into logic,
C7 into economics. Each is independently useful, each is testable, and none requires believing anything about AI
that isn't already demonstrable. Build order: C6 → C1 → C2 → C3 (each shippable, each compounding), with C5 as a
cheap early win in the agent service, and C4/C7 pursued only once the ledger holds enough real engagement history
to fit anything honestly.

*goNXT · What Comes Next is Built Here — and here, it is proven. · Advanced Concepts*
