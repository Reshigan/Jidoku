# Cloudflare deployment — build order (see docs/JIDOKA_DEPLOYMENT_AND_KNOWLEDGE_SPEC.md Part B)
1. Terraform: Access apps (roles builder/reviewer/approver/auditor via client IdP), R2 (EU), Queues, AI Gateway.
2. `EngagementLedger` Durable Object: port jidoka_core/ledger.py semantics to TS (append/approve/verify_chain);
   SoD from Access identity claims, never from request bodies.
3. Org onboarding worker: provision D1-per-tenant from template, R2 prefix, per-tenant envelope key, AI budget.
4. Containers: run ghcr.io/gonxt/jidoka-agent + adapters unchanged (phase 1); Workers-native kernel is phase 2.
5. Edge Connector per client network via Cloudflare Tunnel (deploy/docker/connector-compose.yml).
Invariant: every gate that exists in jidoka-core must exist identically here before any tenant goes live.

## Phase 1 — what actually deploys today
`wrangler.toml` publishes `src/index.ts`: static console from `apps/web/dist` plus an API passthrough
to the Python kernel at `KERNEL_URL`. It implements **no gate**. Every invariant lives once, in
`jidoka-core`; a second copy at the edge is a second copy that can drift out of agreement with the
tested one. `wrangler.phase2.toml` holds the DO/D1/R2/Queues shape for the Workers-native port, and
is not deployed — a binding whose class does not exist fails the deploy.

## CI/CD
`.github/workflows/deploy.yml` runs on merge to `main`. It needs, set by a human in GitHub and
never passed through any other channel:

| Where | Name | Value |
|---|---|---|
| Repository **secret** | `CLOUDFLARE_API_TOKEN` | A **scoped** token: Workers Scripts:Edit, Workers Routes:Edit, Account Settings:Read on this account only. Never the Global API key — it is unscopeable and carries billing. |
| Repository **secret** | `CLOUDFLARE_ACCOUNT_ID` | The account ID. |
| Repository **variable** | `KERNEL_URL` | `https://` origin of the FastAPI kernel (a hostname, not a credential). |

Until `KERNEL_URL` is set the console deploys and serves, and every API call returns a 503 saying
the kernel is unreachable — deliberately, rather than a blank screen.

## The kernel origin
Phase 1 runs `services/api/Dockerfile` wherever containers run (`deploy/docker`, Cloudflare
Containers, or any host reachable over TLS). It must be started with a real `JIDOKA_OIDC_ISSUER`
so `auth.py` refuses the dev token path — with OIDC configured there is no fallback, which is the
point: a fallback is a bypass.
