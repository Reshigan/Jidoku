# goNXT JIDOKA — FULL FEATURE SPECIFICATION v1.0
## Method: every feature is derived from a Komatsu artefact we built by hand
The Komatsu SF greenfield pack is JIDOKA's requirements document, discovered through practice. Each hand-built
artefact below becomes a platform feature; the mapping is the product spec AND the sales narrative:
*"we ran this engagement manually once — JIDOKA is that engagement, generalised and executable."*

---

## DOMAIN 1 — INTAKE & DESIGN

**F1.1 Intake Studio (workbook lifecycle).** Platform issues adapter-specific data-collection workbook templates, tracks return/sign-off per owner per country, compiles signed cells to IR with provenance.
*Komatsu example:* the 13-tab config + 12-tab data collection workbooks, chased by email today → issued, tracked, and compiled inside JIDOKA; an unsigned tab is visibly blocking its dependent build tasks on the plan.

**F1.2 Design Workspace (documents become views).** Functional/Technical Config Specs are rendered FROM the IR, not written beside it — change the IR, every document regenerates; documents can never disagree with the build again.
*Komatsu example:* Functional Config Spec v3.0 drifting from BCUI reality is today's silent risk; in JIDOKA the spec IS the IR rendered in goNXT theme.

**F1.3 Option Sandbox (inverted fit-gap).** For contested DESIGN DPs, JIDOKA builds both options in the twin (or a sandbox tenant) so the business selects by using, not by meeting.
*Komatsu example:* the fit-gap acceleration approach on our horizon — productised: DP carries two twin-simulated options with side-by-side behaviour traces attached to the decision brief.

**F1.4 Fit-to-Standard Budget.** The delta pool as a live counter: every deviation from delivered best practice consumes budget, with rationale; Steering sees the gauge.
*Komatsu example:* the 30-change pool across four countries — today a principle in a document; in JIDOKA a hard counter the plan enforces (31st delta = COMMERCIAL DP, not a quiet commit).

## DOMAIN 2 — PLANNING & EXECUTION

**F2.1 Run-Plan Engine.** Dependency-ordered, tier-split, per-instance plans derived from the IR graph (built, tested).
*Komatsu example:* the Master Build Runbook's P0→P10 with its hand-drawn dependency graph → generated; the runbook becomes a themed rendering of the live plan.

**F2.2 Execution Workspace.** Snapshot→Execute→Validate→Approve/Rollback per task; SoD; one-way badges; sequence locks with logged overrides; per-instance state. (Built as the console; ports to the API per ROADMAP E7.)
*Komatsu example:* GONXT_Build_Checkpoint_Console.html, 48 tasks — the platform's beating heart, discovered on this engagement.

**F2.3 Rollback Planner.** Every plan step auto-carries its layer's revert procedure, snapshot prerequisites, and one-way flag from the adapter's revert matrix.
*Komatsu example:* the Rollback & Checkpoint Framework §01 matrix and six one-way doors → machine-attached to steps instead of living in a PDF nobody opens at 2am during cutover.

**F2.4 Promotion Engine (substrate-aware).** DEV→TEST→PROD paths per product: numbered sync releases (SF), transport releases (ABAP), Terraform plans (BTP); each promotion a ledgered checkpoint.
*Komatsu example:* the Instance-Sync control sheet with SYNC-YYYYMMDD-nn releases and the "what never syncs" table → executable promotion rules, not tribal knowledge.

**F2.5 Cutover Orchestrator.** Timed rehearsal mode (captures actuals at dress rehearsal), go/no-go gate with named approvers, pre-agreed fallback plan attached, hour-by-hour execution with live checkpoint status.
*Komatsu example:* Cutover Runbook v2.0 + DP-B09 fallback ("stay on legacy input one cycle") + MS-09/10 — orchestrated, with the dress-rehearsal timings auto-compared to the cutover window.

## DOMAIN 3 — GOVERNANCE & EVIDENCE

**F3.1 Decision Engine + Brief Generator.** Typed DPs (built); auto-generated decision briefs with options, twin-simulated consequences, recommendation-with-rationale.
*Komatsu example:* DP-B01…DP-B12, DP-M00…: today a register we maintain; in JIDOKA each DP arrives at its owner as a one-page goNXT-themed brief, and unresolved DPs visibly block exactly the plan steps they gate.

**F3.2 Controls Library & Evidence Assembler.** J-SOX controls as objects (CC-01 sync control, CC-03 one-way apjidokal, C-RBP-01/02 SoD, C-PAY-01 bank-detail dual apjidokal); evidence auto-filed against each control from ledger entries, import job IDs, hashes; one-click auditor export, offline-verifiable chain.
*Komatsu example:* SCN-001 rev C's 15 controls and 42 documents, assembled by hand → the Evidence Assembler's first library; the auditor walkthrough becomes an export button.

**F3.3 Hash-chained Ledger.** (Built, tested, tamper-evident.)
*Komatsu example:* the console's JSON/CSV audit log, upgraded to cryptographic.

## DOMAIN 4 — VERIFICATION & TESTING

**F4.1 Verification Suite.** Adapter-templated report packs — reconciliation, duplicates, orphan refs, hierarchy integrity, parity checks, SoD reviews — scheduled per load cycle, results ledgered.
*Komatsu example:* R-01…R-10 defined by hand → instantiated from the SF adapter's report templates the moment an engagement selects the SF product.

**F4.2 Edge-Case Grammar & Persona Factory.** Register entries become generative dimensions (country × event × timing boundary × data shape); synthetic personas exercise them nightly against the twin.
*Komatsu example:* EC-01…EC-24 — EC-10 "leap-day birthday" stops being one row and becomes every date-boundary persona across ZAF/NAM/BWA/MOZ, generated.

**F4.3 Twin & Drift Service.** Schema-exact validation (built); nightly extract→diff→classify (approved vs unauthorised change)→regression; fidelity % published.
*Komatsu example:* the nightly artefact consistency scans we run on documents, elevated to the system itself.

**F4.4 Test & UAT Management.** Scripts generated from IR + grammar; control tests for the controls library; UAT execution tracked as checkpoints with country sign-offs.
*Komatsu example:* Test Strategy v3.0's scripts (incl. the named termination/HRIS-sync deactivation script) → generated and tracked, entry/exit criteria wired to MS-06/07.

## DOMAIN 5 — MIGRATION & LANDSCAPE

**F5.1 System Registry & Landscape Graph.** (Built: roles, write-locks, promotion paths.) Visual estate map.
*Komatsu example:* KOM-ECC-PRD as read-only source, SF DEV/TEST/PROD chain, iFlow endpoints — one screen.

**F5.2 Migration Workbench.** Source introspection, lineage mapping (unmapped-but-populated = forced decision), target-native artefact generation, three-point reconciliation.
*Komatsu example:* the 18-step import sequence + load-control reconciliation signed per country → the workbench's reference flow; PERNR→person-id lineage recorded, not remembered.

## DOMAIN 6 — PROGRAMME & STAKEHOLDER

**F6.1 Milestone Engine.** Earned-not-asserted status from checkpoint linkage (built in console); baseline management with re-baseline control; slip-trigger escalations.
*Komatsu example:* Milestone Register v1.0 + the rail; the "≥3-day slip at MS-04/05 escalates with recovery options" rule becomes an automatic Steering item.

**F6.2 Stakeholder Reporting Generator.** Steering decks, status packs and evidence summaries rendered from live plan/ledger/milestones in client theme (pptx pipeline).
*Komatsu example:* the 28-slide steering deck built by hand → generated Friday 16:00, every number traceable to a ledger entry; the goNXT brand system is theme #1.

**F6.3 Portfolio View.** All engagements, waves, improvement curves, approver workload (the real bottleneck at scale) across GONXT's book.

## DOMAIN 7 — AI CONSULTANT

**F7.1 K5 Agent (builder-only, built as harness).** Tool-use over the API; approve endpoints structurally absent.
**F7.2 Governed Skill Library + K5 Exam.** Skills promote only on exam pass; exam grows from real failures.
*Komatsu example:* the sf-sequencing skill IS the Runbook's hard-won ordering; exam item K5-003 IS the "don't launch comp before perf closes" judgment; K5-004 IS our refusal to browser-script Provisioning.
**F7.3 Instruction-Sheet Generator.** Tier-C human steps with expected before/after values; agent verifies the human's work by diff.
*Komatsu example:* the data-model upload procedure with Git hashes and Check Tool gates → generated per step, per instance.

## DOMAIN 8 — OPERATIONS & HYPERCARE

**F8.1 Hypercare Mode.** Post-go-live drift monitoring, incident intake routed to DPs/defects, control-operation evidence (quarterly R-08 access review auto-scheduled).
*Komatsu example:* Runbook v2.0 hypercare + MS-13 closure evidence pack → a mode, not a document.

**F8.2 Release-Readiness Automation.** Per SAP half-year release: metadata diff → impact classification → regression subset → readiness report.
*Komatsu example:* the release-note review the team would do manually next 1H → a nightly job with a bigger diff.

---

## COVERAGE CHECK (the honest ledger of this spec)
Built and tested today: F2.1, core of F2.2, F3.1, F3.3 gates, F5.1, F7.1 harness, seeds of F1.1/F4.1/F7.2.
Everything else is specified with a Komatsu artefact as its acceptance example — which is the point: **the
acceptance test for every JIDOKA feature is "can it produce what we hand-built for Komatsu, from the IR, on demand."**
That is a falsifiable definition of done for the whole platform.

*goNXT · What Comes Next is Built Here · JIDOKA Feature Specification*
