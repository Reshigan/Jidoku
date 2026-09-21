"""Controls, run over the whole population, on demand (C6).

Read-only and gated on `read`: an auditor asks this more often than anybody and it changes
nothing. The write-locked systems come from the registry rather than from the control module,
because the registry is the authority on roles and a control that decided for itself which
systems were read-only would be checking its own opinion.
"""
from fastapi import APIRouter, Depends
from jidoka_core.controls import run_all
from jidoka_core.registry import WRITE_FORBIDDEN_ROLES

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/controls", tags=["controls"])


@router.get("")
def controls(eid: str, identity: Identity = Depends(require("read"))):
    e = get_or_404(eid)
    locked = {s["system_id"] for s in e.registry.landscape()["systems"]
              if s["role"] in WRITE_FORBIDDEN_ROLES}
    return run_all(e.ledger.entries, write_locked=locked)
