"""The thing a scheduler runs: work the night on every engagement, once.

The night shift itself is a call (ADR-0027). This is what makes it a shift: one entry point with
no scheduler of its own, so cron, a Kubernetes CronJob, a systemd timer, a Cloudflare trigger or a
person at a terminal can all be the clock. Putting the clock inside the process would have meant
one deployment shape, and the platform runs in two by design.

It works in-process against the same store the API serves, which is what makes it safe to run
beside the API in a container: one ledger, one set of gates, no second code path to a customer's
systems. Where the kernel is elsewhere — the edge, a queue worker — the same thing is reachable
over HTTP as POST /engagements/{eid}/nightshift, and the Worker's scheduled handler uses that.

Exit code is 0 when every engagement was worked, 1 when any was not. A scheduler needs to be able
to tell, and a night that half-ran and reported success is worse than one that reported failure.
"""
from __future__ import annotations

import argparse
import json
import sys

from .auth import Identity
from .routers.nightshift import nightshift
from .state import STORE

#: Who the night runs as. Not a person and never pretending to be: the ledger records the platform
#: doing platform work, and every gate it passes through is a gate a person's token would face.
NIGHT_ACTOR = "jidoka.nightshift"


def work_the_night(budget: int = 3, actor: str = NIGHT_ACTOR) -> dict:
    """Every engagement the store holds, one night each. Returns a summary per engagement.

    One engagement failing does not stop the others: a night that abandoned twelve engagements
    because the thirteenth had no connector bound would be worse than useless.
    """
    identity = Identity(subject=actor, roles=("builder",))
    worked, failed = [], []
    for engagement in STORE.list():
        eid = engagement.engagement_id
        try:
            out = nightshift(eid, budget=budget, identity=identity)
        except Exception as ex:                  # noqa: BLE001 — one bad engagement is not the night
            failed.append({"engagement_id": eid, "name": engagement.name,
                           "error": f"{type(ex).__name__}: {ex}"})
            continue
        worked.append({"engagement_id": eid, "name": engagement.name,
                       "client": engagement.client,
                       "findings": len(out["interrupted"]) + len(out["waited"]) + len(out["deferred"]),
                       "interrupted": out["budget"]["spent"],
                       "handover": out["handover"]})
    return {"worked": worked, "failed": failed}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Work the night shift on every engagement.")
    parser.add_argument("--budget", type=int, default=3,
                        help="interruptions allowed per engagement (default 3)")
    parser.add_argument("--actor", default=NIGHT_ACTOR)
    parser.add_argument("--quiet", action="store_true",
                        help="summary only; the handovers are on the ledger either way")
    args = parser.parse_args(argv)

    out = work_the_night(budget=args.budget, actor=args.actor)
    if args.quiet:
        print(json.dumps({"worked": len(out["worked"]), "failed": len(out["failed"])}))
    else:
        for night in out["worked"]:
            print(night["handover"], end="\n\n")
        for bad in out["failed"]:
            print(f"! {bad['engagement_id']} ({bad['name']}): {bad['error']}", file=sys.stderr)
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
