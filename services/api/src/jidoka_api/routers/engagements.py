import uuid

from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.lifecycle import PHASES, TRANSITIONS, LifecycleError, assert_transition
from pydantic import BaseModel

from ..auth import Identity, require
from ..state import STORE, Engagement

router = APIRouter(prefix="/engagements", tags=["engagements"])


class EngagementIn(BaseModel):
    name: str
    client: str


@router.post("")
def create(body: EngagementIn, identity: Identity = Depends(require("write_ir"))):
    eid = str(uuid.uuid4())[:8]
    e = STORE.create(eid, body.name, body.client)
    e.ledger.append("ENGAGEMENT", "CREATED", identity.subject, f"{body.client}:{body.name}")
    return {"engagement_id": eid, "phase": e.phase}


@router.get("")
def list_all(identity: Identity = Depends(require("read"))):
    return [{"engagement_id": e.engagement_id, "name": e.name, "client": e.client, "phase": e.phase,
             "ir_records": len(e.ir), "ledger_entries": len(e.ledger.entries)} for e in STORE.list()]


def get_or_404(eid: str) -> Engagement:
    e = STORE.get(eid)
    if e is None:
        raise HTTPException(404, "engagement not found")
    return e


@router.get("/{eid}")
def detail(eid: str, identity: Identity = Depends(require("read"))):
    e = get_or_404(eid)
    return {"engagement_id": e.engagement_id, "name": e.name, "client": e.client, "phase": e.phase,
            "next_phases": list(TRANSITIONS[e.phase]), "phases": list(PHASES),
            "ir_records": len(e.ir), "open_decision_points": e.open_dps,
            "ledger_entries": len(e.ledger.entries)}


class PhaseIn(BaseModel):
    to: str
    actor: str = ""


@router.post("/{eid}/phase")
def advance_phase(eid: str, body: PhaseIn, identity: Identity = Depends(require("approve"))):
    """Phase advance is an approval-grade act: it declares work complete, so it needs approve authority."""
    e = get_or_404(eid)
    try:
        assert_transition(e.phase, body.to)
    except LifecycleError as ex:
        raise HTTPException(409, str(ex))
    frm, e.phase = e.phase, body.to
    e.persist_header()
    e.ledger.append("ENGAGEMENT", "PHASE_ADVANCED", body.actor or identity.subject, f"{frm} -> {body.to}")
    return {"engagement_id": eid, "phase": e.phase, "from": frm}
