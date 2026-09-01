# The kernel on Fly

The edge Worker (`deploy/cloudflare`) serves the console and proxies every API path to `KERNEL_URL`.
This is what runs at that URL. Until it exists the Worker answers 503 on `/health`, `/engagements`
and friends, by design — see `deploy/cloudflare/src/index.ts`.

## One-time setup

```sh
fly auth login
fly apps create jidoka-kernel
fly volumes create jidoka_data --size 10 --region jnb   # the ledger lives here
```

The store is sqlite on that volume, not a managed Postgres. `jidoka-core` is stdlib-only by charter,
so `open_repository` speaks `sqlite:///path` and nothing else. That is a deliberate constraint, and
it has a consequence: **one machine, never two.** Two writers on one sqlite file corrupt the hash
chain, and a corrupted chain is indistinguishable from tampering — which is the one thing the ledger
exists to rule out. Scaling out is a repository change with an ADR first, `fly scale` second.

## Identity — do this before the first real engagement

```sh
fly secrets set \
  JIDOKA_OIDC_ISSUER=https://login.microsoftonline.com/<tenant-id>/v2.0 \
  JIDOKA_OIDC_AUDIENCE=<app-id> \
  JIDOKA_OIDC_GROUP_MAP='{"<group-guid>":["builder"],"<other-guid>":["approver"]}'
```

With `JIDOKA_OIDC_ISSUER` set, `/auth/token` refuses to mint and only IdP-signed JWTs are accepted.
Without it the dev token path is live, and anyone who can reach the host can mint an approver. There
is deliberately no fallback: a fallback is a bypass. A group granting both `builder` and `approve` is
refused at startup — invariant 7 holds at configuration time, not just at request time.

## Deploy

```sh
fly deploy --config deploy/fly/fly.toml --remote-only    # from the repo root
```

CI does this on every merge to `main` (`.github/workflows/deploy.yml`, job `kernel`), before the edge
job publishes the Worker. It needs one repository secret, `FLY_API_TOKEN` (`fly tokens create deploy`)
— scoped to this app, never a personal org-wide token.

## Then point the edge at it

Set the repository **variable** `KERNEL_URL` to `https://jidoka-kernel.fly.dev` (or a custom domain).
It is a variable rather than a secret because it is a hostname; the kernel refuses every
unauthenticated call on its own. Setting it also un-skips both deploy jobs.

## Health

`/health` reads the store. A machine that cannot see its volume answers 503, never takes traffic, and
the release rolls back — which is the point of it not being a static `{"status":"ok"}`.
