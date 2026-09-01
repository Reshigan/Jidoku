# JIDOKA RULES CODEX v1.0 — DISTILLED DELIVERY KNOWLEDGE
Status: **T2 DRAFT** — practitioner knowledge distilled for the skill library; per our own governance every rule
below requires a named senior's signature (Skill Factory pipe 1) before it grounds production behaviour. The codex
enters through the same gate it describes. Format per rule: the RULE · WHY (the failure it prevents) · GATE (how
JIDOKA enforces, tests, or examines it).

---

## PART 1 — DATA MIGRATION LAWS

**R-101 · Identifiers are forever.** Person/user/business-partner keys outlive every system that mints them.
WHY: rekeying live populations breaks integrations, history, and statutory filings simultaneously; there is no
cheap recovery. GATE: ID-strategy decisions are ONE_WAY ceremonies (built); the planner refuses loads before the
strategy DP closes.

**R-102 · Foundation data is effective from the beginning of time (1900-01-01), not from build day.**
WHY: any migrated history predating a FO's start date fails row-level validation weeks later, in bulk, at the
worst moment. GATE: adapter validators reject FO effective dates after the earliest migrated employment date.

**R-103 · Reconciliation is three-point or it is theatre.** Source → staged → target, counts and value samples.
WHY: two-point recon hides transformation loss; "counts match" says nothing about content. GATE: F5.2 recon is a
checkpoint that cannot be approved with a missing leg.

**R-104 · Migrate the minimum history that satisfies statute and reporting; archive the rest readable.**
WHY: every migrated year multiplies mapping, validation and defect surface; nostalgia is not a requirement.
GATE: history depth is a named DP with a cost line per year, decided by the client, never defaulted.

**R-105 · Test with production-shaped data, never with clean samples.** WHY: real data contains the leap-day
birthdays, the double-barrelled 60-character surnames, the 1970 hire with seven rehires — clean samples validate
nothing but optimism. GATE: the persona factory generates production-shaped populations; mock loads must use them.

**R-106 · The last 5% of data quality costs half the migration effort — plan it, don't discover it.**
WHY: the long tail is manual, per-record, and owned by the client's data owners, who must be staffed for it.
GATE: load reports classify rejects by fixability owner from mock 1; the curve is shown at Steering, early.

**R-107 · Opening balances carry their context or they lie.** A leave balance without its cycle start date, an
accumulator without its period, is a number pretending to be a fact. WHY: recalculation engines will "correct"
context-free balances into statutory violations. GATE: balance import schemas require the context fields; recalc
is disabled during load and run targeted after (encoded in the SF adapter skill).

## PART 2 — INTEGRATION LAWS

**R-201 · Idempotency or incidents.** Every interface must survive being run twice. WHY: retries are not an edge
case, they are Tuesday; non-idempotent loads duplicate money and people. GATE: loader contract requires upsert
semantics + replay journal (built into E3 spec); adapter certification tests replay.

**R-202 · Exactly one system masters each field.** WHY: bidirectional mastery guarantees oscillation and silent
overwrites; "both can edit" is a data-corruption design. GATE: the IR carries a mastery declaration per
integrated field; conflicting declarations block the plan.

**R-203 · An error queue without a named human owner is a data graveyard.** WHY: alerts fatigue; queues grow;
month-end finds them. GATE: integration go-live checklist requires a named owner + SLA per queue; hypercare mode
reports queue age on the Andon board.

**R-204 · Retroactivity has a horizon in every system; know all of them before the first cross-system change.**
WHY: a retro change legal in system A and impossible in system B is a reconciliation break you created. GATE:
retro-limit register per system pair; pre-transmission checks (Komatsu's R-09, generalised).

**R-205 · Interfaces are tested at peak-shape volume — month-end, year-end, go-live backlog — not at demo volume.**
WHY: throughput, locking and rate limits only fail under load; a 50-record test proves connectivity, nothing else.
GATE: performance step in adapter certification with peak-shape fixtures.

## PART 3 — ABAP-STACK LAWS (S/4, ECC)

**R-301 · Transport sequence is sacred; releasing out of order corrupts the target.** WHY: later transports
assume earlier ones; dependency inversion imports half-objects. GATE: the promotion engine orders transports from
the dependency graph and refuses manual reordering without a ceremony.

**R-302 · Number ranges, and other current-state objects, are never transported.** WHY: transporting a number
range status overwrites the target's counter — duplicate documents follow. GATE: adapter blocklist of
never-transport object types; violations fail plan validation.

**R-303 · Direct changes in production (the SM30 shortcut) are how clean audits die.** WHY: unlogged config drift
is invisible until the auditor diffs — and JIDOKA diffs nightly, so it is visible immediately. GATE: drift
classification flags PROD-only deltas as unauthorised by default; retrofit-to-DEV within 48h (CC-02, generalised).

**R-304 · Client-dependent vs client-independent configuration must be known before the first change, per object.**
WHY: an "innocent" cross-client change lands in every client of the system, including production. GATE: adapter
metadata tags each object; cross-client changes are flagged ceremonies.

## PART 4 — CUTOVER LAWS

**R-401 · Rehearse against the clock, not the checklist.** WHY: the dress rehearsal's product is *timings*; a
checklist that fits no window is fiction. GATE: Cutover Orchestrator captures rehearsal actuals and refuses a
cutover plan whose critical path exceeds the window (built into F2.5 spec; Komatsu MS-08→MS-10).

**R-402 · The fallback is decided when calm, executed without debate.** WHY: 2am is not a decision-making
environment; improvised fallbacks fail twice. GATE: go/no-go gate requires an attached, pre-approved fallback
(DP-B09 pattern) before it will open.

**R-403 · Freeze means freeze.** Every "small exception" during cutover invalidates reconciliation baselines.
WHY: the recon you signed no longer describes the system you cut over. GATE: freeze window locks Tier-A writes
platform-wide except the cutover plan itself; exceptions are ledgered ceremonies.

**R-404 · Hypercare is staffed by the people who built it.** WHY: transition-to-support during the highest-defect
fortnight doubles resolution time exactly when it matters most. GATE: hypercare roster check in the go-live gate;
a handover date inside hypercare fails the checklist.

## PART 5 — TESTING & QUALITY LAWS

**R-501 · Negative tests are where the audit lives.** Proving the system *prevents* the wrong thing outranks
proving it does the right thing. WHY: controls testing is negative testing; a pass-only suite certifies nothing.
GATE: every control in the library requires at least one refusal test; the grammar generates violation attempts.

**R-502 · A defect downgraded at the gate returns at month-end with interest.** WHY: severity negotiation under
date pressure converts known defects into production incidents with worse timing. GATE: downgrades at exit gates
are ledgered with the downgrader's name and revisit at the first month-end review — accountability changes the
negotiation.

**R-503 · UAT discovers requirements, not just defects; budget for what it finds.** WHY: users meeting the real
system generate the truest requirements of the programme — a plan with zero UAT-change allowance is a plan to
fail its users or its dates. GATE: delta pool (F1.4) reserves explicit UAT allowance; consumption is visible.

## PART 6 — DESIGN & SCOPE LAWS

**R-601 · Fit-to-standard is a budget, not a slogan.** WHY: unpriced deviations accumulate into an unmaintainable
system one reasonable exception at a time. GATE: the delta counter (built as F1.4 spec); deviation N+1 is a
COMMERCIAL DP.

**R-602 · Every custom field is a twenty-year commitment** — through every release, integration, report and
migration to come. WHY: creation is an afternoon; the lifetime is the cost. GATE: custom-object DPs carry a
lifetime-cost note in the decision brief, not just a build estimate.

**R-603 · The standard is documented; your customisation is folklore.** WHY: SAP maintains its behaviour's
documentation; yours lives in a leaver's head — unless the spec is generated from the IR (F1.2), which is the cure.
GATE: customisations without rendered documentation fail the artefact consistency check.

**R-604 · Reversibility asymmetry governs decision timing: decide late what you can, early what you must.**
WHY: early irreversible decisions made with least information, late reversible ones hoarded as fake progress —
both are planning failures. GATE: every DP is tagged reversible/one-way at creation; the planner surfaces one-way
DPs by required-by date, reversible ones by cheapest-last.

## PART 7 — PROGRAMME & HUMAN LAWS

**R-701 · A steering committee that is informed but never decides is a risk, not a governance body.** WHY: undecided
programmes decide by drift, which is the most expensive deciding there is. GATE: Steering packs lead with the
decision queue; DPs aging past threshold escalate automatically with a cost-of-delay line.

**R-702 · Scope freezes before dates harden — never the reverse.** WHY: confident dates on an unfrozen baseline
are the programme lying to itself in public (the Komatsu steering principle, generalised). GATE: milestone
baselining requires a scope-freeze ledger entry as a prerequisite.

**R-703 · A slip announced early is a plan; announced late it is a crisis.** WHY: the information is identical —
the reaction time is not. GATE: earned milestone status makes concealment structurally impossible; slip triggers
fire at threshold, not at confession.

**R-704 · The client who cannot name data owners has told you the real project risk.** WHY: unowned data is
unfixable data (see R-106); ownership gaps surface as migration failure months later. GATE: engagement onboarding
requires named owners per data domain before load milestones can baseline.

**R-705 · Consultants who interpret statutes are manufacturing liability, not adding value.** WHY: the standing
principle — statutory parameters enter signed by the client's authority or not at all. GATE: STATUTORY DP type
(built); refusal integrity is a scored exam section; 100% required.

## PART 8 — ESTIMATION LAWS

**R-801 · Configuration is a third of the work; the other two-thirds is deciding, moving data, testing, and
proving.** WHY: estimates built from config-object counts miss the majority cost and fail on schedule, not effort.
GATE: the estimator (future feature) prices DPs, data, testing and evidence as first-class lines, never as
percentage uplifts.

**R-802 · Countries multiply where you least model it: statutory content, testing, sign-off latency — not build.**
WHY: four countries is not 4× build, but it is close to 4× decisions and approvals — the human critical path.
GATE: per-country DP and approval-latency tracking on the portfolio view; the approver bottleneck made visible.

---

## HOW THE CODEX LIVES
Every rule maps to at least one of: a gate already built, an adapter validator, an exam scenario, or a decision-
brief clause. Rules without a gate are marked ASPIRATIONAL and are not claimed. Each rule carries provenance on
signing (which senior, which engagement scars). The codex is versioned, exam-linked, and revocable — a rule
invalidated by a platform or SAP change is retired by release-readiness, not by memory.

*goNXT · What Comes Next is Built Here — and here, it is proven. · JIDOKA Rules Codex (T2 draft pending senior signature)*

## PART 9 — CROSS-COUNTRY DESIGN LAWS (from the Komatsu rapid model-company pack)
**R-901 · One global job catalogue; countries vary pay grades, legal entities and statutory fields — never jobs.**
WHY: per-country catalogues quadruple maintenance and break global reporting. GATE: compiler convention; job-object
IR with country binding fails validation.
**R-902 · Country-suffix event reasons only where statutory meaning genuinely differs.** WHY: suffix inflation
recreates four systems inside one. GATE: suffix requires a statutory-difference note in the IR source.
**R-903 · Never assume a currency in a rule, report or mapping.** WHY: NAD≠ZAR is the local proof; hardcoded
currency is a silent cross-border defect. GATE: currency-literal detector on rules/report definitions.
**R-904 · Leave types are country-specific by construction; never parameterise one shared type across regimes.**
WHY: a 36-month sick cycle and a monthly accrual are different machines, not different settings. GATE: shared
leave-type across countries blocks the plan.
**R-905 · Work schedules are statutory inputs where law says so (NAM); model them, don't default the five-day week.**
WHY: entitlement is computed from them — a defaulted schedule is a statutory miscalculation. GATE: schedule DPs
per country before Time Off build tasks unlock.
