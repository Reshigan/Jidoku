# JIDOKA Roadmap — epics broken to Claude-Code-sized issues

A box is ticked only against code that exists and tests that run. Under-reporting misleads exactly
as much as over-claiming, which is why `docs/CLAIMS.md` exists — and why E1–E5 and E7 sat unticked
for weeks after they were built, until somebody checked.

## E1 Core hardening
- [x] Persist ledger/IR/registry to SQLite behind repository interfaces (keep in-memory impl for tests)
      — `jidoka_core.repository`, both implementations held to one suite by `test_repository.py`
- [x] IR JSON Schema published + versioned (ir/v1) — `jidoka_core.schema`, served at `/schema/ir`
- [x] Planner: parallel-branch output (independent subgraphs → concurrent lanes) — `plan()["lanes"]`
## E2 API completeness
- [x] Engagement lifecycle states (DISCOVER→SCOPE→BUILD→CUTOVER→HYPERCARE) — `jidoka_core.lifecycle`,
      forward-only and ledgered
- [x] AuthN/Z: OIDC, roles (builder/reviewer/approver/auditor); SoD enforced server-side — `oidc.py`,
      `auth.py`; a group map granting a builder `approve` is refused at config load (ADR-0008)
- [x] Evidence export endpoint (ledger chain + artefact bundle, auditor-verifiable offline) — `evidence.py`,
      with the verification procedure shipped inside the bundle
## E3 SuccessFactors live path
- [x] OData client (OAuth SAML bearer), $metadata fetch, live extract behind adapter fetcher
- [x] $batch loader with per-record error journal + idempotent replay
- [x] Instance file importers for Tier B artefact handoff
- [ ] Nothing above has ever spoken to a live tenant. Every test injects a transport; the SAML assertion is
      read from an env var and nothing mints or refreshes one. See docs/CLAIMS.md.
## E4 Compiler
- [x] XLSX workbook → IR with cell-level provenance (openpyxl), gap questionnaire for prose docs
- [x] Documents projected from signed state, including the archaeology backlog (ADR-0017)
## E5 Agent (K5 consultant)
- [x] Anthropic tool-use loop over API endpoints (agent = builder only) — `consultant.py`; the tool list
      excludes approval, and no ring an agent occupies holds the capability
- [x] K5 exam runner: YAML scenarios, human-graded rubric ingestion, pass-gate for skill promotion —
      `exam.py`, `grader.py`; a skill is examined only on its own syllabus (ADR-0011)
## E6 Twin v1
- [x] Rule-export parser → executable rule eval; fidelity published as a projection over the chain and withheld
      below ten settled predictions; the twin never blocks a write (ADR-0026). SAP's own rule XML is not parsed —
      the evaluatable subset is JIDOKA's shape and refuses what it cannot read.
## E7 Web app
- [x] Port checkpoint console to React on live API; milestone rail; DP queues; landscape graph — 15 screens,
      state from the API and never local truth, every endpoint walked by a browser in `e2e/coverage.spec.ts`
## E8 New adapters
- [~] S/4HANA adapter: OData writes, CSRF, and transport-aware completion DEV→QA→PROD are built (ADR-0006,
      ADR-0009). BC Set generation and TMS release hooks are not.
- [ ] BTP adapter via Terraform provider
## E9 Deployment & SaaS
- [ ] EngagementLedger Durable Object (TS port of ledger semantics + Access-identity SoD)
- [ ] Org onboarding worker: D1-per-tenant, R2 prefix, envelope keys, AI Gateway budgets
- [ ] Edge Connector: adapter runtime + tunnel client; ro-binding compiled without write capability
- [ ] Terraform for Access/R2/Queues/DO; GH Actions -> GHCR -> wrangler
## E10 Knowledge & Skill Factory
- [ ] K1 tenant-truth extractor -> graph (nightly)
- [ ] K2 corpus pipeline: release-aware chunks, citation IDs, validity windows (gate: DP-K01 legal review — shut in code, `jidoka_knowledge.corpus.require_open`; brief at docs/decisions/DP-K01.md)
- [ ] Vectorize retrieval with citation-required answers; citation-coverage metric on dashboard
- [ ] Skill Factory: elicitation tooling, engagement mining, senior sign-off flow, K5 exam gate
## E11 Advanced concepts (docs/JIDOKA_ADVANCED_CONCEPTS.md)
- [x] C6 Evidence Compiler: complete-population assurance (`jidoka_core.assurance` — ADR-0023) and controls as
      executable predicates over the ledger (`jidoka_core.controls`: six controls, every row tested, violations
      enumerated rather than counted, NOT_EXERCISED distinguished from PASS — ADR-0025)
- [ ] C1 Refinement-typed IR: statutory/referential refinements; plan type-checking
- [ ] C2 CP-SAT run-planner: optimal sequencing under approver/window/statutory constraints + shadow prices
- [ ] C3 Bayesian forecaster: nightly Monte-Carlo P(go-live) + ranked interventions
- [x] C5 Adversarial agent economy: architect/auditor/sentinel/operator/economist, no shared memory — `jidoka_os.crew`
      runs the pass, `routers/run.py` binds the syscalls to the executor, the Crew view shows who held what authority (ADR-0018)
- [ ] C4/C7 (research): causal defect graph; DP routing mechanism design
## E12 Team-member behaviours (docs/JIDOKA_TEAM_MEMBER_MODEL.md)
- [x] Shift scheduler + night jobs + first-person handover composer (`jidoka_os.handover`,
      `routers/nightshift.py`, the Crew screen — ADR-0027), with a clock in both deployment shapes:
      `python -m jidoka_api.nightly` under compose, a Worker `scheduled()` handler at the edge (ADR-0028)
- [x] Interruption budget ranked by cost-of-silence — published table, hard budget, and what it held back is in
      the handover rather than dropped (ADR-0027)
- [x] Person profiles: authority, named-zone working hours, cheapest-sufficient-authority routing, weekly
      capacity read off the ledger's `ASKED` entries, and observed latency from its DP_RAISED/DP_RESOLVED
      pairs (`jidoka_os.people`, `routers/people.py` — ADR-0029). Capacity changes who is asked and a full
      team is the finding; latency is reported in the handover and deliberately never routed on.
- [x] Self-accountability page: refusals and clearings on the ledger, gates read as friction or as
      holding, drift after a verification counted apart from drift, twin fidelity reused rather
      than recomputed, and what it cannot measure printed beside the numbers
      (`jidoka_core.accountability`, `routers/accountability.py`, the Evidence screen — ADR-0031)
- [x] Portfolio: every engagement at once, worst first, each number the same projection its own
      screen shows (`routers/portfolio.py`, the Portfolio screen — ADR-0032)
- [x] Objection records with revisit triggers: stated once by identity, consequence and
      recommendation required, grounds a closed set, overridden only by a named person holding
      `approve`, revisited at the phase where the consequence lands — and the revisit reports what
      the chain says, never who was right (`jidoka_core.objections`, `routers/objections.py`, the
      night shift's `objection_due`, the Decisions screen — ADR-0033)
## E13 Insight & team (built: jidoka-insight; docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT.md)
- [x] Archaeology reverse-IR (unsigned by construction) · time-travel as_of · person-level blast radius · debt index
- [x] Insight reachable end to end: API (`routers/insight.py`), Insight console view, `archaeology-backlog` document;
      signing a recovered draft makes it ordinary IR the planner, documents and verification already handle (ADR-0017)
- [x] Cross-module contract registry in the IR schema: single owner module, registered consumers,
      what it feeds, statutory linkage. Two writers block the plan through the same gate an open
      decision point uses; an undeclared reader is a finding that names the owner; standard
      configuration needs no contract (`jidoka_core.contracts`, `routers/contracts.py`, the Intent
      screen — ADR-0034)
- [ ] Module agent manifests (RCM/ONB/PMGM/TO) + PMO/migration agent manifests in economy.py
