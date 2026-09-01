# CLAUDE.md — goNXT JIDOKA platform (root)

JIDOKA (自働化 — automation with a human touch) is a SAP automated-configuration platform: signed design intent (Config IR) in → verified
configuration out, executed through each SAP product's native change substrate, under a
hash-chained governance ledger with human-in-the-loop decisioning.

## Monorepo map
- `packages/jidoka-core`      — domain kernel: IR, planner, registry, ledger, decisions, twin. Pure stdlib. Everything depends on this; it depends on nothing.
- `packages/jidoka-os`        — Agent OS: privilege rings, capability-checked syscalls, processes/budgets, shift scheduler, agent economy. Read docs/JIDOKA_AGENT_OS.md.
- `packages/jidoka-knowledge` — memory: evidence-grounded claims, project vs system stores, deterministic staleness, the scrubber gate. Read docs/adr/0010.
- `packages/jidoka-insight`   — archaeology, time-travel, blast radius, technical debt.
- `packages/jidoka-adapters`  — Adapter SDK + product adapters (SuccessFactors is the reference). Depends on jidoka-core only.
- `packages/jidoka-compiler`  — design docs (workbooks) → IR. LLM-assisted, sign-off-gated.
- `services/api`             — FastAPI: engagements, IR, plans, ledger, decisions, registry.
- `services/agent`           — the K5 consultant: Anthropic API + governed skills + eval harness.
- `apps/web`                 — platform UI (React/Vite). `public/legacy-console.html` is the proven checkpoint UX to port.

## Non-negotiable invariants (never weaken these, in any PR, ever)
1. IR records without a signed source are unloadable. No code path may execute unsigned intent.
2. Open decision_points hard-block planning. JIDOKA never invents statutory or client values.
3. SOURCE_LEGACY and TWIN systems cannot hold write credentials (enforced at registration).
4. Ledger is append-only and hash-chained; apjidokal requires reviewer != builder AND a prior snapshot entry.
5. ONE_WAY decisions require two distinct named approvers; STATUTORY require an evidence ref.
6. Tier-A applies default to dry_run=True; arming a live write requires an explicit target + ledger snapshot.
7. The agent is always builder, never approver.

Any change touching these requires a test proving the gate still holds, plus an ADR in docs/adr/.

## Dev workflow
`make setup` → `make test` (all packages) → `make api` (dev server) → `make web`.
Python 3.11+, type hints required, no new runtime deps in jidoka-core (stdlib only — deliberate).
Tests live next to the package they test; every bugfix ships with a regression test.
Conventional commits; CI (`.github/workflows/ci.yml`) must be green before merge.

## Where to start on common tasks
- New SAP product adapter → `packages/jidoka-adapters` (implement `base.Adapter`, declare an honest tier_map, add fixture-driven tests; read ADR-0003).
- New API surface → router in `services/api/src/jidoka_api/routers`, wire in `main.py`, test with httpx TestClient.
- Agent skills → `services/agent/skills/<name>/SKILL.md`; every skill change must pass `services/agent/evals`.
- UI → port interactions from `apps/web/public/legacy-console.html`; state comes from the API, never local truth.

## Deployment
Two modes, one kernel: `deploy/docker` (self-hosted + client-side Edge Connector) and `deploy/cloudflare`
(SaaS: DO ledger, D1-per-tenant, R2 evidence, Queues, Access-based SoD). Read
docs/JIDOKA_DEPLOYMENT_AND_KNOWLEDGE_SPEC.md before touching deploy/. Governance must not vary by hosting.
