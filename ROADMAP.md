# JIDOKA Roadmap — epics broken to Claude-Code-sized issues
## E1 Core hardening (now)
- [ ] Persist ledger/IR/registry to SQLite behind repository interfaces (keep in-memory impl for tests)
- [ ] IR JSON Schema published + versioned (ir/v1)
- [ ] Planner: parallel-branch output (independent subgraphs → concurrent lanes)
## E2 API completeness
- [ ] Engagement lifecycle states (DISCOVER→SCOPE→BUILD→CUTOVER→HYPERCARE)
- [ ] AuthN/Z: OIDC, roles (builder/reviewer/approver/auditor); SoD enforced server-side
- [ ] Evidence export endpoint (ledger chain + artefact bundle, auditor-verifiable offline)
## E3 SuccessFactors live path
- [ ] OData client (OAuth SAML bearer), $metadata fetch, live extract behind adapter fetcher
- [ ] $batch loader with per-record error journal + idempotent replay
- [ ] Instance file importers for Tier B artefact handoff
## E4 Compiler
- [ ] XLSX workbook → IR with cell-level provenance (openpyxl), gap questionnaire for prose docs
## E5 Agent (K5 consultant)
- [ ] Anthropic tool-use loop over API endpoints (agent = builder only)
- [ ] K5 exam runner: YAML scenarios, human-graded rubric ingestion, pass-gate for skill promotion
## E6 Twin v1
- [ ] Rule-export parser → executable rule eval, calibrated against DEV probes; fidelity metric published
## E7 Web app
- [ ] Port checkpoint console to React on live API; milestone rail; DP queues; landscape graph
## E8 New adapters
- [ ] S/4HANA/ECC transport-native adapter (BC Set generation, TMS release hooks)
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
- [ ] C6 Evidence Compiler: controls as executable predicates over ledger+state; complete-population assurance
- [ ] C1 Refinement-typed IR: statutory/referential refinements; plan type-checking
- [ ] C2 CP-SAT run-planner: optimal sequencing under approver/window/statutory constraints + shadow prices
- [ ] C3 Bayesian forecaster: nightly Monte-Carlo P(go-live) + ranked interventions
- [ ] C5 Adversarial agent economy: architect/auditor/sentinel/operator/economist, no shared memory
- [ ] C4/C7 (research): causal defect graph; DP routing mechanism design
## E12 Team-member behaviours (docs/JIDOKA_TEAM_MEMBER_MODEL.md)
- [ ] Shift scheduler + night jobs + first-person handover composer
- [ ] Interruption budget ranked by cost-of-silence
- [ ] Person profiles: authority, capacity, latency, working hours; cheapest-sufficient-authority routing
- [ ] Self-accountability page: fidelity defects, forecast calibration, refusal review
- [ ] Objection records with scheduled revisit triggers
## E13 Insight & team (built: jidoka-insight; docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT.md)
- [x] Archaeology reverse-IR (unsigned by construction) · time-travel as_of · person-level blast radius · debt index
- [ ] Cross-module contract registry in IR schema (owner module, declared readers)
- [ ] Module agent manifests (RCM/ONB/PMGM/TO) + PMO/migration agent manifests in economy.py
