"""Verification: read the live system and compare it to signed intent, record by record.

This is the platform's test run. The expected state is not written by a tester — it IS the signed
IR, so the suite cannot test the wrong thing and cannot go stale. A mismatch is not a red row in
a report: the DriftWatch appends it to the ledger and raises a decision point that blocks
planning until a named human chooses between reasserting the intent and signing new intent
(ADR-0013). Gated on ledger_append: builders and reviewers can both run it, and running it always
writes the ledger.
"""
from fastapi import APIRouter, Depends
from jidoka_core.drift import NOT_APPLIED, DriftWatch

from ..auth import Identity, require
from .engagements import get_or_404
from .execution import _adapter_for

router = APIRouter(prefix="/engagements/{eid}/verification", tags=["verification"])


def run_verification(e, actor: str) -> dict:
    """The verification pass itself, callable without a request.

    The crew run ends with this, and it must be the same pass the Verify screen runs — a platform
    with two verifications has two truths, and the one nobody is looking at is the one that
    quietly goes stale.
    """
    watch = DriftWatch(e.ledger, e.decisions)
    # Only a record this platform has actually written can drift. The ledger is where that is
    # recorded, so it is where the question is asked (ADR-0018).
    applied = {entry.get("task") for entry in e.ledger.entries if entry.get("action") == "EXECUTED"}
    verified, findings, skipped, unbuilt = [], [], [], []
    for r in e.ir:
        connector = e.connectors.get(r.system_binding)
        if connector is None:
            skipped.append({"key": r.key, "reason": f"no connector bound to {r.system_binding} — "
                                                    f"cannot read what cannot be reached"})
            continue
        adapter = _adapter_for(r.product, connector)
        try:
            system = e.registry.get(r.system_binding)
            live = adapter.extract(system, r.object)
            verdict = adapter.verify(r, live)
        except Exception as ex:  # noqa: BLE001 — a record that cannot be read is reported, not fatal
            skipped.append({"key": r.key, "reason": str(ex)})
            continue
        finding = watch.observe(r, verdict, actor, applied=r.key in applied)
        if finding is None:
            verified.append(r.key)
        elif finding.status == NOT_APPLIED:
            unbuilt.append({"key": finding.key, "system": finding.system,
                            "reason": "signed intent describes it; nothing has been written yet"})
        else:
            findings.append({"key": finding.key, "status": finding.status,
                             "system": finding.system, "fields": finding.fields,
                             "decision_point": finding.dp_id})
    e.persist_dps()
    return {"verified": verified, "drift": findings, "skipped": skipped, "not_applied": unbuilt,
            "planning_blocked": bool(findings)}


@router.post("")
def verify(eid: str, identity: Identity = Depends(require("ledger_append"))):
    """Verify every IR record whose system has a bound connector. Reading only — a verification
    that could write would be an execute wearing a lab coat."""
    return run_verification(get_or_404(eid), identity.subject)
