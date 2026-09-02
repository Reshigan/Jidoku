from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.ledger import LedgerTampered, SoDViolation
from pydantic import BaseModel

from ..auth import Identity, require
from ..evidence import build_bundle
from .engagements import get_or_404
from .plans import _plan_or_409

router = APIRouter(prefix="/engagements/{eid}/ledger", tags=["ledger"])


# Actions the kernel writes as proof that something happened. Invariants 4 and 6 read them back
# as preconditions, so a caller that could post them could manufacture its own permission: forge a
# SNAPSHOT and a live write passes the rollback gate having read nothing; forge an EXECUTED under
# the approver's name and approve() locks that approver out of their own task.
RESERVED_ACTIONS = frozenset({"SNAPSHOT", "EXECUTED", "APPROVED", "ARMED", "DISARMED",
                              "ROLLED_BACK", "PHASE_ADVANCED", "DRY_RUN"})


class Entry(BaseModel):
    task: str
    action: str
    detail: str = ""
    # No actor field: the entry is signed by whoever is holding the token, never by whoever asks.


@router.post("")
def append(eid: str, body: Entry, identity: Identity = Depends(require("ledger_append"))):
    e = get_or_404(eid)
    if body.action.upper() in RESERVED_ACTIONS:
        raise HTTPException(403, f"{body.action} is written by the kernel when it does the work, "
                                 f"not by a caller claiming it happened. Use the endpoint that performs it.")
    return e.ledger.append(body.task, body.action, identity.subject, body.detail)


class Approval(BaseModel):
    task: str
    reviewer: str = ""


@router.post("/approve")
def approve(eid: str, body: Approval, identity: Identity = Depends(require("approve"))):
    """SoD is decided by the ledger's history, not by the caller's badge — see auth.py."""
    try:
        return get_or_404(eid).ledger.approve(body.task, body.reviewer or identity.subject)
    except SoDViolation as ex:
        raise HTTPException(403, str(ex))


@router.get("")
def chain(eid: str, identity: Identity = Depends(require("read"))):
    e = get_or_404(eid)
    try:
        e.ledger.verify_chain()
    except LedgerTampered as ex:
        # Surfaced, never swallowed: a broken chain suspends approvals in the console.
        raise HTTPException(409, str(ex))
    return {"verified": True, "entries": e.ledger.entries}


@router.get("/evidence")
def evidence(eid: str, identity: Identity = Depends(require("export_evidence"))):
    """Auditor-verifiable export: chain + SoD attestation + DP register + landscape, offline-checkable."""
    e = get_or_404(eid)
    try:
        p = _plan_or_409(e)
    except HTTPException:
        p = None            # an unplannable engagement still has evidence worth exporting
    return build_bundle(e, p)
