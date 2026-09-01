# JIDOKA — THE AGENT PROJECT TEAM, THE CONNECTION PATH & CROSS-MODULE DESIGN ALIGNMENT v1.0
Worked against the Komatsu SF engagement as the reference medium-size project (4 countries, 5–6 modules, 4 human consultants, 13 build weeks).

---

## 1 · HOW WE ACTUALLY CONNECT AND CONFIGURE (the wire-level answer, Komatsu-concrete)

**Connection, per system, per the registry:**
- **SF DEV/TEST/PROD** — OAuth 2.0 SAML bearer with the X.509 technical user Komatsu IT already scoped (API-only,
  IP-allowlisted to JIDOKA egress / the Edge Connector, RBP-scoped to Tier-A entities). One credential per
  instance, vaulted, never in IR or logs.
- **ECC PRD** — registered SOURCE_LEGACY: the Edge Connector sits inside Komatsu's network (outbound tunnel only),
  holds **read** credentials locally, and is *compiled without write capability* for that binding.
- **Integration Suite** — API deployment credentials for iFlow lifecycle (Tier-A end to end).

**Configuration, per tier, in one sentence each:** Tier A — agents issue `sys_write_tier_a`; the kernel checks
halt→capability→write-lock→budget, the SF adapter builds the OData `$batch`, the connector or SaaS egress executes,
the verifier re-extracts and diffs against IR. Tier B — agents emit import files; a named human runs the two-click
import; the same re-extract/diff verifies the human. Tier C — agents emit instruction sheets with expected
before/after (data-model XML, Provisioning, BCUI rules); human executes; diff verifies. **One verification path
for all three tiers** — that is what keeps mixed human/agent work coherent.

## 2 · THE PROJECT TEAM: PAIRED HUMANS AND AGENT PROCESSES

Not "agents replace the team" — **each scarce human is paired with agent processes that remove everything beneath
their judgment.** Komatsu sizing:

| Human (4 total) | Paired agent processes (ring) | The human now does |
|---|---|---|
| **Reshigan — Engagement Lead** | PMO agent (2): milestone/forecast/steering pack composer · Economist (3) | Steering, client decisions, commercial calls |
| **Clifford — Architect/EC** | Solution-architect agent (2) · Statutory sentinel (2) · Red-team auditor (3) | Design judgment, IR sign-off, quality bar |
| **Lorraine — Talent modules** | Module agents: RCM/ONB/PMGM (2), one process per module, shared skill library | Cross-module design decisions, client workshops |
| **Naveen — Payroll/Time/ECC** | Integration agent (1) · Time Off module agent (2) | ECC mapping authority, statutory intake, payroll recon sign-off |
| **Swatantra — Data & reporting** | Migration agent (2): 18-step orchestration, recon · Verification jobs (1) | Data-owner management, reject disposition, report design |
| **Komatsu approvers** | Decision-brief composer routes to them | Deciding and signing — nothing else |

Agent headcount is elastic (processes spawn per module per instance under budgets); **human headcount stays 4 —
the medium project is delivered at small-project staffing, senior-only.** SoD holds because every agent is Ring
1–3: builder at most, approver never; every approval is one of the five humans or Komatsu.

## 3 · HOW CUSTOMISATIONS ARE DESIGNED AND HANDLED ACROSS MODULES

The Komatsu lesson: a customisation is never module-local. `custom-string4` (MIBCO flag) is *written* by EC,
*read* by Time Off eligibility, EE reporting, and the ECC payroll interface. Handle it as a **cross-module
contract**, not a field:

**Lifecycle of every customisation (no exceptions):**
1. **Trigger** — a gap the delivered standard cannot meet, evidenced against the baseline extract (never "preference").
2. **Design brief** — options incl. the standard-workaround option, **lifetime cost** (R-602: twenty-year
   commitment priced), and the blast radius at person level.
3. **Delta pool debit** — consumes one of the 30 (F1.4); pool empty ⇒ COMMERCIAL DP, not a quiet build.
4. **Contract registration in the IR** — the object declares: single **owner module** (writes), registered
   **consumers** (read), the propagation/interface mappings it feeds, and its statutory linkage if any.
5. **Build → verify → regression grammar** picks it up automatically as a new test dimension.
6. **Every SAP release**, release-readiness re-validates the contract (custom objects are the release-risk surface).

**Rule that keeps modules from colliding:** *one writer, declared readers.* A second module wanting to write the
same object is a plan-blocking conflict (R-202 generalised from integration to modules) that forces a design
decision instead of a silent race.

## 4 · HOW THE DESIGN STAYS ALIGNED (the honest answer: it cannot drift, structurally)

Alignment on human projects is a meeting; here it is a property, from five mechanisms already built or specced:
1. **One IR.** Every module agent, every human, every document reads the same graph. There is no "EC version of
   the design" to diverge from the Time Off version.
2. **Documents are views** (F1.2). The Functional Spec cannot disagree with the build because it is rendered from it.
3. **Blast-radius propagation.** Any accepted change computes its cross-module radius; affected artefacts and
   module agents are re-run or flagged — the consistency reflex from the Cognitive Architecture, mechanical.
4. **Nightly drift service.** Tenant vs IR, per instance; unauthorised deltas classified and surfaced by morning
   handover. Alignment decays in days elsewhere; here it is re-proven every 24 hours.
5. **The economy argues before humans commit.** Architect vs auditor vs sentinel objections are logged on every
   cross-module design; a customisation arrives at Clifford with its cross-module challenges already documented.

The Komatsu proof-case: when scope moved (rollback → modules → milestones), the whole artefact set was
reintegrated each time. Section 4 is that behaviour with the human (me, then) replaced by machinery that cannot
forget to do it.

*goNXT · What Comes Next is Built Here — and here, it is proven.*
