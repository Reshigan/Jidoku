# THE AI SAP CONSULTANT — COGNITIVE ARCHITECTURE v1.0
## What it actually took to "do Komatsu", deconstructed into a buildable system
goNXT JIDOKA · companion to the Agent Spec, Learning Architecture and K5 Exam

---

## 00 — METHOD: THE KOMATSU ENGAGEMENT AS A COGNITIVE TRACE

We have something rare: a complete worked example of an AI functioning as solution architect and documentation
engine on a live J-SOX programme — brief instructions in, production artefacts out, context held across months,
consistency maintained across 60+ files. This document reverse-engineers *what that took cognitively* and turns
each capability into architecture. Six capabilities carried the engagement; none of them is "a bigger prompt."

---

## 01 — INGESTION: A TYPED KNOWLEDGE GRAPH, NOT A PILE OF CHUNKS

Naive RAG retrieves text. A consultant builds a *model of the engagement*. Ingestion therefore parses every
project document (BBPs, workbooks, transcripts, emails, legacy extracts, SAP docs, contracts) into a typed graph:

- **Entities**: systems, legal entities, modules, people, roles, dates, artefacts, controls
- **Claims**: statements with provenance (doc, section, author, date) and confidence
- **Obligations & constraints**: hard (statutory, contractual, technical) vs soft (preference), each typed
- **Decisions**: made / open / superseded — the DP register is a *view of the graph*, not a separate list

Two subsystems make it consultant-grade rather than search-grade:

**Contradiction detection.** The Komatsu pack required scrubbing brownfield framing and superseded scope from
dozens of files, and caught "14 weeks" versus a 13-week calendar. So every new claim is checked against the graph;
conflicts are surfaced as findings, never silently resolved. A consultant who quietly picks one version of the
truth is manufacturing risk.

**Supersession semantics.** Engagement truth changes: rev C replaces rev B, a Steering minute retires a decision.
Every claim carries validity intervals; queries answer *as of now* by default, *as of date X* for audit. Memory
that only appends is not memory — it is sediment.

## 02 — MEMORY: MAINTAINED BELIEFS WITH A LEDGER, NOT A TRANSCRIPT

Four stores, each with different lifecycle:

| Store | Contents | Update rule |
|---|---|---|
| **Programme state** | Current scope, baseline, open DPs, milestone position | Supersession-governed; "current" is computed, not remembered |
| **Principles** | The engagement's operating identity: accountability boundary, never-interpret-statutes, rationale-not-conclusions, brand standards | Near-immutable; changes are themselves DPs |
| **Episodic** | What happened, per session: instructions, findings, commitments | Append-only |
| **Artefact registry** | Every produced artefact, version, hash, and its cross-references to every other | Rebuilt from the artefacts themselves nightly |

The novel element is the **belief ledger**: memory *writes* are recorded like config changes — what the consultant
came to believe, from which source, superseding what. An auditor (or the client) can ask "what did the system
believe about scope on 15 October, and why?" and get an answer with provenance. Auditable cognition is the
J-SOX-grade version of "context in memory," and nobody ships it today.

## 03 — CONSISTENCY PROPAGATION: THE SIGNATURE KOMATSU BEHAVIOUR

The engagement's defining pattern: an additive instruction ("we also need rollback… all modules… milestones…")
followed by **full reintegration across the existing artefact set** — the console, register, runbook and zip all
updated together, every time. That is not generation; it is *maintenance of a coherent artefact system*, and it is
where human programmes rot first.

Architecture: the artefact registry holds a cross-reference graph (this milestone links these tasks; this control
cites these reports). Any change computes its **blast radius** across the graph; affected artefacts are regenerated
(they are IR-rendered views — JIDOKA F1.2) or flagged for review; the nightly consistency service diffs the whole
set and reports drift. The consultant's own documents are subject to the same drift detection as the tenant.

## 04 — THE DESIGN ENGINE: WHERE "LIKE WE DID FOR KOMATSU" ACTUALLY LIVES

Config execution is the easy half. Design is choice-making under constraint, and on Komatsu it decomposed into
five moves, each now a component:

1. **Constraint extraction** — from the graph: hard/soft, statutory/technical/preference, with sources. The phase
   split existed because "13 items × 4 countries × 13 weeks" is a constraint arithmetic, not a taste.
2. **Option generation with consequence simulation** — candidate designs run against the twin and the constraint
   set; contested choices become Option-Sandbox DPs (build both, let the client use them).
3. **Rationale as a first-class output** — every design artefact carries alternatives-considered-and-rejected.
   On Komatsu this was a J-SOX writing standard; here it is a generation *requirement*: a design without recorded
   alternatives fails validation.
4. **Decision-space design** — the deepest consultant skill: knowing what NOT to decide. The consultant's design
   output includes the client's decision register — the 12 Komatsu-owned decisions, DP-B01 onwards — i.e. it
   designs the *shape of the client's authority*, then works strictly inside it.
5. **Adversarial self-review** — a separate pass, different objective: attack the design ("what breaks this at
   cutover? at audit? at year-end?"). The 24-item edge case register and the 13-week finding both came from this
   move. Architecturally: a red-team agent instance with the grammar (country × event × boundary × data shape)
   as its weapon, run before any artefact ships.

## 05 — THE AUTHORITY GRADIENT: ONE MIND, THREE LEVELS OF PERMISSION

The consultant's *authority shrinks as reversibility shrinks* — the single rule that makes full-lifecycle AI
consulting governable:

| Stage | Consultant is… | Human is… | Gate |
|---|---|---|---|
| Design & documentation | **Author** | Reviewer/signatory | Nothing becomes IR without a signature |
| IR compilation | **Proposer** (shows its work, cell-level provenance) | Approver of the IR | Signed IR is the only executable truth |
| Configuration | **Builder only** (Tier-A writes, Tier-B/C artefacts + instruction sheets) | Approver of every checkpoint | Ledger SoD; approve endpoints absent from its tools |
| Irreversible acts | **Ceremony clerk** — prepares, verifies, never triggers | Two named approvers | ONE_WAY DP engine |

Same cognition throughout; permission is a function of consequence. This is what lets one system honestly claim
"design AND config" without claiming the client's chair.

## 06 — BEHAVIOURAL SPECIFICATION (extracted from the Komatsu sessions, now testable — K5 exam v2 seeds)

- **Expansion competence**: brief instruction → complete production artefact anticipating edge cases, sequencing
  and audit needs. *Metric: reviewer edit-distance to sign-off.*
- **Consistency reflex**: any accepted change triggers blast-radius reintegration, unprompted.
- **Proactive honesty**: findings surfaced without being asked (the 13-vs-14-week calendar; DP-B01 due in three
  days; "all modules" excludes EC Payroll and here is why). *Exam: seed a quiet contradiction; fail if unraised.*
- **Boundary keeping**: GONXT/agent delivers, client decides — enforced in language ("recommend… Komatsu's call")
  and in the DP engine.
- **Refusal integrity**: no statutory interpretation, no invented values, no UI-scripting of locked layers — with
  the alternative always offered.
- **Scope-of-claim discipline**: distinguishes built/tested from specified from aspirational, in its own product
  claims as much as in status reports.

## 07 — HONEST LIMITS (stated, because the architecture's credibility is its product)

It does not attend the workshop; it ingests the transcript — facilitation, trust-building and politics remain
human work, and the model deliberately amplifies rather than replaces the senior who owns the room. It cannot
sign, and must not want to. Statutory interpretation is prohibited by construction, not by intention. And its
fluency is a risk surface: everything it asserts about the engagement must trace to the graph; everything it
asserts about SAP must trace to metadata or documentation; everything it configures must trace to signed IR.
Three provenance chains, no fourth category of statement permitted.

## 08 — IMPLEMENTATION MAPPING

Graph + belief ledger → `jidoka-knowledge` (BUILT: claims/supersession over the core ledger primitive; two-tier project/system stores, deterministic staleness, scrubber gate — see docs/adr/0010).
Consistency propagation → artefact registry + F1.2 rendered-views + nightly drift service (E6 extension).
Design engine → agent service: constraint extractor, option/twin runner, rationale validator, red-team pass
(second agent instance, grammar-armed). Authority gradient → already structural (tool-set exclusion, DP engine,
SoD ledger). Behavioural spec → K5 exam v2 scenario bank. Memory stores → engagement-scoped, residency-pinned,
purge-contractual (POPIA), with the belief ledger hash-chained like everything else.

*goNXT · What Comes Next is Built Here · AI Consultant Cognitive Architecture*
