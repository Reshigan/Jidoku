# goNXT JIDOKA — SAP AUTOMATED CONFIGURATION PLATFORM
## Product Specification v1.0
Working name JIDOKA (fits the tagline; final name is Reshigan's call). Scope: all SAP products. Purpose: load an engagement — scope, design, decisions, like the Komatsu pack — and the platform runs the configuration in, with human-in-the-loop decisioning, migration source/target management, and full large-programme governance.

---

## 00 — PRODUCT THESIS

Every SAP implementation on earth burns the same effort: interpreting design docs, sequencing dependencies, keying config, testing it, and evidencing it. JIDOKA industrialises that: **design in → verified configuration out**, with humans doing only what machines cannot (decide, approve, and touch the UI-locked layers). The Komatsu engagement is the reference implementation: everything built there — Config IR, checkpoint lifecycle, tiered automation, twin, governed learning — generalises. JIDOKA is that generalisation productised.

What is genuinely different from every "AI for SAP" tool in market: (1) it writes through each product's **native change-control substrate** (transports for ABAP-stack, Instance Sync/imports for SF, APIs for BTP) instead of around it; (2) every value traces to a signed source; (3) the AI consultant is **certified against an exam graded by real senior consultants** and its knowledge is under change control; (4) verification is automated even where writes are manual.

---

## 01 — PLATFORM ARCHITECTURE (seven layers)

```
L1  ENGAGEMENT      workspaces · scope · waves · milestones · RAID · steering packs
L2  CONSULTANT AI   LLM core · skill library · citation-RAG · certification harness
L3  CONFIG IR       universal intermediate representation · compiler from design docs
L4  ADAPTERS        one per SAP product · declares its tier map, extractor, loader, verifier
L5  EXECUTION       run-planner · loaders · digital twins · diff/verify · repair loop
L6  GOVERNANCE      HITL decision engine · checkpoints · SoD · one-way doors · audit ledger
L7  SYSTEM REGISTRY source & target systems · connectivity · credentials · landscape map
    ─ cross-cutting: tenancy & client-data isolation · security · evidence store ─
```

---

## 02 — L7 SYSTEM REGISTRY: CAPTURING SOURCE & TARGET SYSTEMS (the migration question)

Every system an engagement touches is a first-class registered object:

```json
{ "system_id": "KOM-ECC-PRD", "product": "SAP ECC 6.0 EhP8", "role": "SOURCE_LEGACY",
  "environment": "PROD", "landscape": "KOM-HR-2026",
  "connectivity": {"protocol": "RFC+OData", "auth": "technical_user", "vault_ref": "…", "network": "customer_vpn"},
  "extraction_profile": {"read_only": true, "windows": "22:00-04:00 SAST", "pii_classes": ["national_id","bank"], "residency": "ZA"},
  "owner": "Komatsu IT", "change_substrate": "TMS transports" }
```

Rules: roles are explicit (SOURCE_LEGACY / TARGET / DEV / TEST / PROD / TWIN / SANDBOX); **source systems are cryptographically read-only** — the platform physically cannot hold write credentials for a system registered as source; every environment pair (DEV→TEST→PROD) forms a promotion path the governance layer enforces; the landscape map renders the whole estate as a graph so a programme director sees every system, every interface, every promotion path on one screen.

**Migration workbench (source→target):**
1. **Introspect** source: schema, config tables, data profile (volumes, null rates, format anomalies) — read-only extract.
2. **Map** in the lineage workbench: source field → IR → target field; every mapping row carries transform rule, owner, sign-off; unmapped-but-populated source fields are surfaced as *forced decisions*, not silently dropped (a classic migration failure, structurally prevented).
3. **Generate** target-native migration artefacts: Migration Cockpit templates for S/4, the 18-step import set for SF, LSMW-successor formats for ECC — the adapter decides the vehicle.
4. **Reconcile**: automated three-point recon (source count → staged → target) + value-level sampling + lineage-complete report. Recon is a checkpoint; a human signs it; the platform assembled the evidence.

---

## 03 — L4 ADAPTER FRAMEWORK: ALL SAP PRODUCTS, HONESTLY TIERED

An adapter is a contract: `extract() · validate(ir) · plan(ir) · apply(plan) · verify(ir) · tier_map`. The tier map declares, per config object class, whether it is API-writable (A), file-automatable (B), or UI-locked (C) — the Komatsu analysis, done once per product, versioned per release:

| Adapter | Write substrate | Tier profile (approx) |
|---|---|---|
| SuccessFactors | OData / imports / Provisioning | A 70% · B 20% · C 10% (built — reference adapter) |
| S/4HANA on-prem & ECC | **Transports (CTS/TMS)**: config written via BC Sets/API into a transport request; promotion = transport release, apjidokals map to ChaRM/Cloud ALM | A+B high — the ABAP stack is *more* automatable than SF because transports are a real API-era change substrate |
| S/4HANA Cloud Public | Central Business Configuration APIs, scope-item activation, Cloud ALM | A high, C low |
| BTP / Integration Suite | Full APIs + official Terraform provider | A ~100% — true config-as-code |
| Ariba / Concur / Fieldglass | Admin APIs + UI-locked admin panels | A/B moderate, C meaningful — tier maps per module |
| ECC payroll/time (PTP era) | Transports + schema/PCR objects | B-heavy; PCR/schema generation with human import |

Key architectural point: **the platform never invents a change path.** If SAP's substrate is a transport, JIDOKA writes a transport. If it is a UI, JIDOKA writes an instruction sheet and verifies by extract-diff. Adapters are certified per SAP release (the release-readiness automation from the learning architecture, generalised).

---

## 04 — L3 CONFIG IR & ENGAGEMENT LOADING (how a "Komatsu pack" goes in)

Engagement intake pipeline: **Design docs (workbooks, BBP/FS docs, decision registers) → Compiler → IR + Decision Point set + dependency graph + tier-split run plan.** The compiler is LLM-assisted but *sign-off-gated*: humans approve the IR against the source docs before it becomes executable truth (the compiler shows its work — every IR value hyperlinked to the source cell/paragraph). Prose-only design docs are accepted but downgraded: the compiler emits a structured gap questionnaire instead of guessing — exactly what a senior consultant does with a vague spec.

The universal IR extends the SF schema with product namespace, system binding, and migration lineage refs, so one engagement can span SF + ECC + BTP objects in a single dependency-sorted plan — which is what real programmes are.

---

## 05 — L6 GOVERNANCE: HITL DECISION-MAKING AS AN ENGINE, NOT A MEETING

Decision objects are typed and routed:

| DP type | Examples | Routing |
|---|---|---|
| DESIGN | option A/B config choices | Product owner queue; twin can pre-build both options (the inverted fit-gap from Komatsu, productised) |
| STATUTORY | leave rules, ID formats, tax refs | **Hard block**: platform is structurally incapable of inventing these; only a signed client source unblocks |
| ONE-WAY | purges, launches, first replication, ID strategies | Dual-apjidokal, named client approver, rehearsed rollback note required to even open the gate |
| SEQUENCE | overrides, re-baselines | Logged exceptions with reason |
| COMMERCIAL | scope/licence/wave | Steering queue with auto-generated decision brief |

Every DP carries an auto-generated **decision brief** (options, consequences, twin-simulated impact where possible, recommendation with rationale) — humans decide *well* because the machine prepared the decision. Checkpoints, SoD (builder ≠ reviewer; AI is always builder, never approver), milestone rail earned-not-asserted, and the append-only evidence ledger all carry over from the Komatsu console, which becomes JIDOKA's execution UI.

## 06 — L1 LARGE-PROGRAMME MANAGEMENT

Waves and workstreams are graph partitions of the IR dependency graph — the plan is *derived from the work*, not drawn in PowerPoint and reconciled later. Milestones bind to checkpoint sets (earned status); RAID items link to DPs and drift reports; steering decks and J-SOX evidence packs are generated artefacts (the pptx pipeline from Komatsu, templated); resource model maps named humans to roles per workstream with SoD checked across the whole programme, not per task. Multi-engagement portfolio view for GONXT: every client, every wave, every improvement curve.

---

## 07 — L2 THE CONSULTANT AI: MAKING IT A GENUINE K5-GRADE SENIOR CONSULTANT

Honest engineering position: nobody "trains an LLM to be a senior consultant" by pouring PDFs into fine-tuning. Consultant-grade capability is a **system**, and it is certified, not claimed:

1. **Frontier model core, model-agnostic harness.** Best available reasoning model per task tier; heavy design judgment on the frontier model, high-volume validation distilled to cheaper models. Benchmarked quarterly — the harness outlives any one model.
2. **Citation-required knowledge.** RAG over: SAP Help/implementation guides, release notes per product per release, adapter tier maps, and GONXT's governed skill library. The model may not state a config fact it cannot cite to metadata, documentation, or a signed engagement source. Folklore answers fail evals.
3. **Governed skill library** (from the learning architecture): the distilled judgment of real seniors — sequencing playbooks, edge-case grammars, "what Clifford checks before a legal-entity load" — versioned, eval-gated, compounding across engagements with client values scrubbed.
4. **The K5 Certification Exam — the load-bearing idea.** A bank of scenario evaluations *authored and graded by named human senior consultants* (Clifford/Lorraine-grade cross-checkers), covering: dependency sequencing under constraint, defect diagnosis from reject logs, DP recognition (does it block on unsigned statutory values?), design challenge (does it push back on a bad client design, with rationale?), estimation sanity, migration mapping judgment, and refusal integrity (does it decline to guess?). Every model+skill+prompt version must pass ≥ threshold on the current exam before production deployment; the exam itself grows from real engagement failures. **"Best trained K5 consultant" is therefore a certificate with a score and a date, renewed per version — not a marketing sentence.**
5. **Behavioural spec of a K5 senior** encoded as testable properties: challenges designs; never invents statutory or client values; escalates early with options; sequences before configuring; writes rationale, not just conclusions; treats every irreversible act as a ceremony. (Readers of the Komatsu pack will recognise this list — it is that engagement's operating principles, made executable.)

---

## 08 — TENANCY, SECURITY, IP

Per-client engagement stores: encrypted, region-pinned (POPIA/GDPR residency from the system registry), purge terms contractual and executable. Cross-engagement learning takes *shapes only* through the scrubber gate — client values never enter the shared skill library. Credentials vaulted, never in IR or logs; source systems write-locked at the credential layer; the platform's own admin actions are subject to the same checkpoint ledger it imposes on engagements (it eats its own governance).

## 09 — BUILD ROADMAP

| Stage | Ships | Proof point |
|---|---|---|
| 1 (now→Q1 27) | SF adapter (extract/diff/loader — already specced), console→platform UI, system registry v1, IR compiler v1 | Komatsu Wave 2 runs ON the platform |
| 2 (H1 27) | Twin v1, K5 exam v1 + governed skills, migration workbench v1 | Measured improvement curves on a live client |
| 3 (H2 27) | S/4/ECC adapter (transport-native) + BTP adapter (Terraform) | First cross-product engagement |
| 4 (2028) | Ariba/Concur/S4 Public Cloud adapters; portfolio layer; external licensing of JIDOKA | Platform revenue independent of GONXT delivery hours |

DP-F01 (Reshigan/GONXT board): platform investment case & build-vs-partner for adapter engineering. DP-F02: productisation vs internal-tool line (licensing JIDOKA changes GONXT's business model). Both deserve their own briefs.

*goNXT · What Comes Next is Built Here · JIDOKA Platform Specification · GONXT (NXT Business Solutions (Pty) Ltd t/a GONXT), Lanseria Corporate Park, Johannesburg*
