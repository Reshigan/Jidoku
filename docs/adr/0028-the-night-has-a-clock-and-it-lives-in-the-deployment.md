# ADR-0028 — The night has a clock, and it lives in the deployment

Status: Accepted
Date: 2026-09-21
Relates to ADR-0027 (the night shift). Completes E12's first item.

## Context

ADR-0027 built the night shift and left it a call somebody makes. That is a shift only in the
sense that a gym membership is exercise. The obvious fix — a scheduler inside the kernel — would
have picked one deployment shape, and the platform runs in two by design: self-hosted Docker and
a Cloudflare edge, with the deployment spec insisting governance must not vary by hosting.

There was also a lie to clean up. `docker-compose.prod.yml` listed a `jobs` service pointing at
`ghcr.io/gonxt/jidoka-jobs:latest`, an image this repository does not build — the same shape as
the Edge Connector: a compose file describing infrastructure nobody can start.

## Decision

**One entry point, no clock of its own.** `python -m jidoka_api.nightly` works the night on every
engagement the store holds and exits 0 or 1. Cron, a Kubernetes CronJob, a systemd timer, a
Cloudflare trigger or a person at a terminal can all be the clock. Exit code matters: a scheduler
needs to know, and a night that half-ran and reported success is worse than one that failed.

**One engagement failing does not abandon the others.** A night that stopped at the first
engagement with no connector bound would leave twelve unworked. Failures are collected, printed to
stderr, and reflected in the exit code.

**It runs as the platform, not as a person.** `jidoka.nightshift` holds `builder` and nothing
more. Every gate it passes is the gate a person's token would face, and the ledger records the
platform doing platform work rather than a human who was asleep.

**Two clocks, one shift.** In Docker, a `nightshift` service running *the API image* calls the
entry point in-process — one kernel, one code path to a customer's systems, no second image. At
the edge, `scheduled()` in the Worker POSTs `/engagements/{eid}/nightshift` for each engagement
using a `NIGHT_TOKEN` secret; it reimplements nothing, because the shift, its budget and its
handover live in one tested place and the edge only decides *when*.

**An unconfigured night says so.** With no `KERNEL_URL` or no `NIGHT_TOKEN` the scheduled handler
logs and refuses rather than calling a customer's kernel unauthenticated. A silent no-op is a
shift nobody knows stopped happening, and `routing.check.mjs` asserts that refusal exists.

## Consequences

- The night is now a property of a deployment rather than of somebody's memory. Both shapes are
  checked in CI: the Python entry point by its tests, the Worker by `routing.check.mjs` and a
  `wrangler --dry-run` that validates the cron.
- The compose file no longer references an image that does not exist. The queue consumers from the
  deployment spec are still unbuilt, and now say so in a comment rather than in a service block.
- A sleep loop is what compose can express. Under an orchestrator this is a CronJob, which is why
  the entry point does not care what calls it.

## Alternatives rejected

*A scheduler inside the kernel.* APScheduler or a thread. It would have worked, and it would have
put the clock in the one place the deployment spec says must behave identically everywhere —
including in a test process, where a thread waking at 02:00 to write to customer systems is not a
thing anybody wants.

*Let the Worker work the night itself.* It would need the ledger, the gates, the controls, the
twin. ADR's phase-1 rule holds: every invariant reimplemented in a second language is an invariant
that can drift out of agreement with the tested one.
