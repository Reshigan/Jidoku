from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.decisions import DecisionError, DecisionPoint
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/decisions", tags=["decisions"])


class DPIn(BaseModel):
    dp_id: str
    dp_type: str
    question: str
    owner: str
    options: list[str] = []


@router.post("")
def raise_dp(eid: str, body: DPIn, identity: Identity = Depends(require("raise_dp"))):
    e = get_or_404(eid)
    try:
        e.decisions.raise_dp(DecisionPoint(body.dp_id, body.dp_type, body.question,
                                           body.owner, body.options))
    except DecisionError as ex:
        raise HTTPException(422, str(ex))
    e.persist_dps()
    return {"raised": body.dp_id}


@router.get("")
def list_dps(eid: str, identity: Identity = Depends(require("read"))):
    e = get_or_404(eid)
    dps = [{"dp_id": d.dp_id, "dp_type": d.dp_type, "question": d.question, "owner": d.owner,
            "options": d.options, "resolution": d.resolution} for d in e.decisions.dps.values()]
    return {"decision_points": dps,
            "unresolved": [d["dp_id"] for d in dps if not d["resolution"]],
            "ir_gaps": e.open_dps}


class Resolution(BaseModel):
    decided_by: str = ""
    value: str
    evidence_ref: str = ""
    second_approver: str | None = None


@router.post("/{dp_id}/resolve")
def resolve(eid: str, dp_id: str, body: Resolution,
            identity: Identity = Depends(require("resolve_dp"))):
    e = get_or_404(eid)
    try:
        dp = e.decisions.resolve(dp_id, body.decided_by or identity.subject, body.value,
                                 body.evidence_ref, body.second_approver)
    except DecisionError as ex:
        raise HTTPException(403, str(ex))
    except KeyError:
        raise HTTPException(404, "DP not found")
    e.persist_dps()
    return {"resolved": dp_id, "resolution": dp.resolution}
