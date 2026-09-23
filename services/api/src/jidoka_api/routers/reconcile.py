"""The product's own change log against this ledger.

This closes the gap `CLAIMS.md` has named as the platform's most expensive one since ADR-0031:
work that never reached a gate. Everything else here reads the chain, so a change made by hand in
the SAP GUI is not under-reported — it is invisible, and every number this platform publishes was
computed as if it had not happened.

It is also, deliberately, the answer to the free competitor. SuccessFactors ships Change Audit and
SAP positions it for detecting unexpected changes; reconciling it against the ledger is not
competing with it, it is consuming it.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.reconcile import WINDOW_MINUTES, reconcile

from ..auth import Identity, require
from .engagements import get_or_404
from .execution import _adapter_for

router = APIRouter(prefix="/engagements/{eid}/reconcile", tags=["reconcile"])

#: The ledger action. Written on every run so a reconciliation that stopped happening is visible,
#: for the same reason the night shift's silence is (ADR-0030).
RECONCILED = "RECONCILED"


@router.post("")
def run_reconcile(eid: str, system_id: str, since: str = "",
                  identity: Identity = Depends(require("ledger_append"))):
    """Read the system's change log and say what happened there that never came through here."""
    e = get_or_404(eid)
    try:
        system = e.registry.get(system_id)
    except Exception:                        # noqa: BLE001
        raise HTTPException(422, f"{system_id} is not registered on this engagement.") from None

    connector = e.connectors.get(system_id)
    adapter = _adapter_for(system.product, connector)
    theirs = adapter.change_log(system, since) if connector else None
    if theirs is None:
        # Never an empty list. A reconciliation that found nothing and one that could not look
        # produce the same number and mean opposite things.
        raise HTTPException(409, adapter.cannot_read_changes())

    designed = {r.key for r in e.ir if r.system_binding == system_id}
    ours = [x for x in e.ledger.entries if x.get("task") in designed]
    out = reconcile(ours, theirs, designed)

    e.ledger.append(system_id, RECONCILED, identity.subject, out["says"],
                    out_of_band=len(out["out_of_band"]), matched=len(out["matched"]))
    for finding in out["out_of_band"]:
        e.ledger.append(finding["object"], "OUT_OF_BAND", identity.subject, finding["says"],
                        changed_by=finding["by"], at=finding["ts"])
    return {**out, "system_id": system_id, "since": since}


@router.get("")
def last_reconcile(eid: str, identity: Identity = Depends(require("read"))):
    """What the chain says about out-of-band changes, and whether anybody has ever looked.

    A projection, so a restart cannot lose it — and an engagement nobody has reconciled says so
    rather than reporting a clean result it never earned.
    """
    e = get_or_404(eid)
    runs = [x for x in e.ledger.entries if x.get("action") == RECONCILED]
    found = [{"object": x.get("task"), "says": x.get("detail"), "by": x.get("changed_by", ""),
              "at": x.get("at", "")}
             for x in e.ledger.entries if x.get("action") == "OUT_OF_BAND"]
    return {"ever_run": bool(runs), "runs": len(runs),
            "last_run": runs[-1]["ts"] if runs else "",
            "out_of_band": found,
            "window_minutes": WINDOW_MINUTES,
            "says": ("Nobody has reconciled this engagement against the systems' own change logs, "
                     "so every number here assumes nothing was done outside the platform — which "
                     "is an assumption, not a finding."
                     if not runs else
                     f"{len(found)} change(s) to designed configuration were made outside the "
                     f"platform." if found else
                     f"Reconciled {len(runs)} time(s); no change to designed configuration was "
                     f"made outside the platform.")}
