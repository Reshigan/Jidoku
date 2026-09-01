from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.ledger import LedgerTampered, SoDViolation
from pydantic import BaseModel

from ..auth import Identity, require
from ..evidence import build_bundle
from .engagements import get_or_404
from .plans import _plan_or_409

router = APIRouter(prefix="/engagements/{eid}/ledger", tags=["ledger"])


class Entry(BaseModel):
    task: str
    action: str
    actor: str = ""
    detail: str = ""


@router.post("")
def append(eid: str, body: Entry, identity: Identity = Depends(require("ledger_append"))):
    e = get_or_404(eid)
    return e.ledger.append(body.task, body.action, body.actor or identity.subject, body.detail)


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
