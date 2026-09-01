from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.planner import PlanError, plan

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/plan", tags=["plans"])


def _plan_or_409(e):
    try:
        return plan(e.ir, e.open_dps)
    except PlanError as ex:
        raise HTTPException(409, str(ex))   # 409: open DPs / cycles block the plan by design


@router.post("")
def build_plan(eid: str, identity: Identity = Depends(require("plan"))):
    e = get_or_404(eid)
    p = _plan_or_409(e)
    e.ledger.append("PLAN", "BUILT", identity.subject, f"{len(p['steps'])} steps {p['tier_summary']}")
    return p


@router.get("")
def current_plan(eid: str, identity: Identity = Depends(require("read"))):
    """Read the plan without ledgering a rebuild — the console polls this."""
    return _plan_or_409(get_or_404(eid))
