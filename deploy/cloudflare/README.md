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
| Repository **variable** | `KERNEL_URL` | `https://` origin of the FastAPI kernel (a hostname, not a credential). |
| Repository **secret** | `CLOUDFLARE_ACCOUNT_ID` | Optional. `account_id` is committed in `wrangler.toml` — it is an identifier that grants nothing — so this is only needed by a fork deploying to a different account. Set, it wins; unset, it is ignored rather than blanking the config. |
| Repository **secret** | `FLY_API_TOKEN` | Only if the kernel job publishes to Fly. Skipped with the rest of the pipeline until `KERNEL_URL` is set. |

Until `KERNEL_URL` is set the console deploys and serves, and every API call returns a 503 saying
the kernel is unreachable — deliberately, rather than a blank screen.

### Where the night's interruptions go
`JIDOKA_NOTIFY_URL` is the webhook the night shift posts an interruption to — Slack, Teams,
Opsgenie, or anything that accepts a POST. Unset, the night still works and still writes its
handover; it says plainly that the interruptions had nowhere to go and nobody was told, rather
than letting "I woke somebody twice" imply otherwise. The URL is a credential in every practical
sense: set it as a secret, never in a file, and note that only what the interruption budget spent
is ever sent (ADR-0040).

### The one secret CI cannot set
`NIGHT_TOKEN` is a **Worker** secret, not a repository secret, because nothing in the pipeline
should be able to mint the token the night shift calls the kernel with. Set it once, by hand:

```
cd deploy/cloudflare && npx wrangler secret put NIGHT_TOKEN --env production
```

It is a builder token and nothing more — the night reads, verifies and chases, and every gate it
meets is the gate a person's token meets (the agent is never an approver, invariant 7). Until it
is set, the 02:00 cron refuses and logs *"KERNEL_URL or NIGHT_TOKEN is not configured — no night
was worked"* rather than calling a customer's kernel unauthenticated. Check it is there the minute the deploy finishes:

```
curl -s https://jidoka.vantax.co.za/__edge
{"kernel_url":true,"night_token":true,"night_armed":true,"detail":"The edge is configured and the night shift will run."}
```

Booleans only, never the values — the point is to catch a secret that was never set or has since
been rotated, and printing it would be the leak the check exists to prevent. `night_armed: false`
means the 02:00 cron will fire and do nothing.

After that the platform watches itself: the Crew screen reports when no night has been worked in
over 36 hours, read off the ledger rather than out of the API's memory (ADR-0030). A night shift
nobody knows stopped happening is worse than one that never started.

## The kernel origin
Phase 1 runs `services/api/Dockerfile` wherever containers run (`deploy/docker`, Cloudflare
Containers, or any host reachable over TLS). It must be started with a real `JIDOKA_OIDC_ISSUER`
so `auth.py` refuses the dev token path — with OIDC configured there is no fallback, which is the
point: a fallback is a bypass.
