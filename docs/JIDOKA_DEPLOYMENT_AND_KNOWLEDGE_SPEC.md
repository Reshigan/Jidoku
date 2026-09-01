# goNXT JIDOKA — DEPLOYMENT & KNOWLEDGE ABSORPTION SPECIFICATION v1.0
Part A: Docker (self-hosted / dev / client-side) · Part B: Cloudflare SaaS · Part C: SAP knowledge corpus ·
Part D: Consulting-skill acquisition. One parity principle throughout: **the same kernel, gates and ledger run
identically in every deployment mode — governance must not vary by hosting.**

---

# PART A — DOCKER DEPLOYMENT (reference stack, and the client-side connector)

## A1. Service topology (docker-compose.prod.yml in deploy/docker/)
| Service | Image | Role |
|---|---|---|
| `api` | jidoka/api | FastAPI over jidoka-core (stateless; N replicas) |
| `agent` | jidoka/agent | K5 consultant workers: tool-use loop, red-team pass, instruction-sheet generation |
| `jobs` | jidoka/jobs | Queue consumers: extract, diff, verification suite, nightly consistency, release-readiness |
| `db` | postgres:16 | Engagement state, IR, plans, DP register (SQLite in dev — same repository interface, E1) |
| `ledger-db` | postgres:16 (separate instance) | Hash-chained ledger + belief ledger, WORM-configured tablespace, restricted role |
| `objects` | minio | Artefact/evidence store (S3 API = R2 parity): IR files, XML deltas, exports, workbooks |
| `vectors` | qdrant | Knowledge embeddings (Vectorize parity) |
| `proxy` | caddy | TLS, mTLS for agent/service traffic |
| `otel` + `grafana/loki` | — | Traces, logs, the improvement-curve dashboards |

Rules: ledger writes go through the kernel only (DB role for `api` has INSERT-only on ledger tables — append-only
enforced at the database layer as well as in code); per-engagement encryption keys via envelope encryption (KMS or
sealed secrets); nightly `db` + `ledger-db` dumps to `objects` with hash manifest — the backup itself is evidence.

## A2. The JIDOKA Edge Connector (the piece everyone forgets)
On-prem ECC/S/4 and IP-allowlisted SF tenants are not reachable from a SaaS. Ship a **client-side connector**: a
single container (adapter runtime + outbound tunnel client) installed inside the client network by client IT.
Properties: outbound-only connection (no inbound firewall holes), executes Tier-A writes and extracts *locally*
under the client's own vaulted credentials, streams evidence back, and honours the registry — a connector bound to
a SOURCE_LEGACY system is compiled without write capability at build time. For Komatsu: one connector beside ECC,
one with SF egress. This is also the data-residency answer: payloads can be confined to client premises with only
hashes, diffs and ledger entries leaving.

---

# PART B — CLOUDFLARE-NATIVE SAAS

## B1. Component mapping (each choice justified)
| Concern | Cloudflare service | Why this is the right primitive |
|---|---|---|
| **Ledger** | **Durable Objects** — one DO per engagement ledger | DOs are single-threaded per object: append ordering and hash-chain integrity are guaranteed by the platform's concurrency model, not by locks we write. The strongest technical fit in the whole mapping |
| Engagement state | D1 — **one database per tenant** | Hard tenant isolation as a property, not a WHERE clause; per-tenant export/purge is a file operation (POPIA purge terms become executable) |
| Artefacts & evidence | R2 (per-tenant prefix + jurisdiction pinning; EU jurisdiction for POPIA-adequate residency) | Zero egress fees matter: evidence bundles are large and auditors download them |
| API + UI | Workers (TS) + Pages | Edge latency for the Andon board; UI reads DO/D1 directly via service bindings |
| Python services (agent, adapters, compiler) | **Cloudflare Containers** phase 1 (run the Docker images unchanged); Workers-native TS port of jidoka-core phase 2 (kernel is small + stdlib-only — deliberately portable) | Honest sequencing: don't rewrite the kernel to launch; don't run containers forever |
| Job orchestration | Queues + Cron Triggers | Load jobs, verification suite, nightly consistency/drift, release-readiness runs |
| Knowledge embeddings | Vectorize (+ Workers AI for embedding generation) | Corpus retrieval at edge; citation IDs stored with vectors |
| LLM traffic | **AI Gateway** in front of Anthropic API | Per-tenant budgets, caching, full request logging — the agent's token spend becomes a governed, auditable meter (and a billable line) |
| AuthN/Z | Cloudflare Access (Zero Trust): OIDC federation to client IdPs (Komatsu Entra ID), service tokens for agent/connector | Roles builder/reviewer/approver/auditor arrive as verified identity claims → **SoD enforced from authenticated identity, not request bodies** (closes ROADMAP E2 properly) |
| SAP connectivity | Cloudflare Tunnel ⇄ Edge Connector (A2) | Outbound-only into client networks; no VPN peering projects |
| Sessions/flags | KV | |
| Audit export | Logpush to client-owned R2/S3 | The client can hold their own copy of everything — trust by architecture |

## B2. Multi-tenancy & isolation model
`Org → Engagement → Instance` hierarchy. Isolation stack: D1-per-tenant + DO namespace per engagement + R2 prefix +
per-tenant envelope keys + AI Gateway budget per tenant. Cross-tenant flows exist in exactly one place — the
**scrubber gate** promoting shapes to the shared skill library — and that gate is itself a ledgered ceremony.

## B3. Delivery pipeline
GitHub Actions: test (the 16-and-growing suite is the merge gate) → build images → GHCR → `wrangler deploy` +
Terraform (Cloudflare provider) for DO/D1/R2/Queues/Access as code. Blue-green via Workers versions; DO migrations
rehearsed against a copy — **the platform's own releases follow jidoka: staged, gated, reversible or ceremonied.**
Compliance path: SOC 2 Type II within 12 months (the hash-chained ledger and Access logs are most of the evidence),
pen test before first external tenant, DR = D1 exports + R2 replication + DO state snapshots, RPO 24h/RTO 4h v1.

---

# PART C — SAP KNOWLEDGE ABSORPTION (what the consultant must know, honestly sourced)

## C1. The four knowledge classes — different physics, different pipelines
**K1 — Tenant ground truth (machine, per engagement).** `$metadata`, data-model XML, delivered best-practice
content, Check Tool results, picklist/role catalogues, rule exports. Source: the client's own tenant. Trust tier
T0 — this outranks every document including SAP's own, because it is what the system *is*. Pipeline: extractor →
graph, refreshed nightly. No licensing issue: customer's data, customer's entitlement.

**K2 — Official SAP corpus (documents, versioned).** Help Portal implementation guides, admin guides, release
notes (2/year × product), API Business Hub specs, SAP Notes/KBAs. Pipeline: acquire → normalise → chunk with
structure preserved → embed (Vectorize) → **every chunk carries product + release-validity window + citation ID**;
retrieval is release-aware (a 1H2025 answer must not ground a 2H2026 build). ⚠ **DP-K01 (legal, before ingestion
at scale):** SAP documentation is copyrighted and Notes are S-user-gated. Position to validate with counsel and
the partner agreement: ingestion for internal retrieval under partner/customer entitlement, citations point to
SAP sources, **no redistribution of SAP content to third parties, ever** — JIDOKA sells judgment grounded in the
corpus, not the corpus. This DP gates the SaaS knowledge feature; do not hand-wave it.

**K3 — Practitioner knowledge (curated, low-trust).** Community posts, blogs, conference material. Tier T3:
advisory signal only, never the sole basis for any claim, always provenance-tagged. Curation is editorial, human,
slow — accept that or poison the well.

**K4 — Engagement-derived knowledge (the moat).** Belief ledgers, reject taxonomies, rollback reasons, instruction-
sheet corrections → scrubbed to shapes → skill candidates. Compounds per Part D. Client values never cross the gate.

**Statutory knowledge is deliberately NOT a class.** The standing principle survives scale: statutes enter only as
client-signed sources per engagement. A knowledge base of "SA leave law" would rot silently and create liability;
the refusal is the feature.

## C2. Corpus scale & sequencing (honest numbers)
SuccessFactors alone: thousands of Help pages × 2 releases/year; ECC/S/4 is an order of magnitude larger, plus
decades of Notes. Therefore: **corpus follows the adapter roadmap** — SF EC + talent first (Komatsu's footprint),
ABAP-stack next, never "all of SAP" as a launch claim. Freshness SLO: new release notes graphed within 7 days
(feeds release-readiness automation); every retrieval answer displays its release-validity window. Metric:
**citation coverage** — % of product-chain statements grounded in T0/T1; target ≥99%, published on the curve
dashboard with the rest.

---

# PART D — CONSULTING-SKILL ACQUISITION (the scarce resource, industrialised)

## D1. Skill taxonomy
| Layer | Examples | Source of truth |
|---|---|---|
| **Craft** (per module) | EC sequencing, Time Off accrual patterns, RBP design, comp cycle mechanics, transport discipline | Named human seniors + K1/K2 corpus |
| **Cross-cutting** | Data migration (18-step pattern), integration (PTP, iFlows), localisation mechanics, cutover | Engagement packs (Komatsu = seed set) |
| **Programme** | Milestone/gate discipline, steering comms, estimation, change control, evidence assembly | The Komatsu artefact→feature map |
| **Judgment** | DP recognition, design challenge, scope defence, statutory refusal, one-way-door instinct | Behavioural spec §06 of the Cognitive Architecture; examined, not asserted |

## D2. The Skill Factory (operating model — this is a staffing decision, not a software feature)
Three intake pipes, one gate: (1) **Elicitation** — structured sessions where a named senior (Clifford-grade)
narrates a task while the platform drafts the SKILL.md + eval set; senior edits and signs; ~1 skill/senior/week is
a realistic cadence. (2) **Engagement mining** — belief-ledger and defect patterns proposed as skill candidates
weekly. (3) **Doc distillation** — K2 corpus compressed into procedure drafts, always senior-signed. Every skill
ships with: provenance (who signed), release-validity, an eval set, and a K5 exam pass. Skills are versioned,
citable, and *revocable* — a skill invalidated by a SAP release is retired by the release-readiness job, not by
memory. The commercial punchline for NTT: **their bench of seniors is the skill factory's feedstock** — JIDOKA
converts scarce senior hours into permanent, examined, licensable capability instead of one-off project hours.

## D3. What the "fully trained consultant" claim means, operationally
It means: T0/T1 citation coverage ≥99% on product claims · current K5 exam passed by the deployed model+skill
version · skill library coverage mapped per module with gaps published · statutory refusal rate 100% on the exam's
trap items · improvement curves public to the tenant. Anything less stays labelled *in training* on the tenant's
own Andon board. The claim is a dashboard, not a sentence.

*goNXT · What Comes Next is Built Here — and here, it is proven. · JIDOKA Deployment & Knowledge Specification*
