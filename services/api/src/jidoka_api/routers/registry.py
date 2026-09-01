from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.registry import RegistryError, SystemRecord, WriteLockViolation
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/systems", tags=["registry"])


class SystemIn(BaseModel):
    system_id: str
    product: str
    role: str
    environment: str
    connectivity: dict = {}
    owner: str = ""
    change_substrate: str = ""
    # The next hop this system promotes into (DEV -> QA -> PROD). Declared here rather than
    # inferred, because a transport route the platform guessed is a route nobody signed off.
    promotes_to: str = ""


@router.post("")
def register(eid: str, body: SystemIn, identity: Identity = Depends(require("register_system"))):
    e = get_or_404(eid)
    fields = body.model_dump()
    promotes_to = fields.pop("promotes_to", "")
    try:
        e.registry.register(SystemRecord(**fields))
        if promotes_to:
            e.registry.add_promotion_path(body.system_id, promotes_to)
    except WriteLockViolation as ex:
        raise HTTPException(403, str(ex))
    except RegistryError as ex:
        # An unregistered promotion target is an unknown key, not a gate violation.
        raise HTTPException(404 if promotes_to else 403, str(ex))
    e.persist_systems()
    e.ledger.append("REGISTRY", "SYSTEM_REGISTERED", identity.subject,
                    f"{body.system_id} role={body.role}")
    return {"registered": body.system_id}


@router.get("/landscape")
def landscape(eid: str, identity: Identity = Depends(require("read"))):
    return get_or_404(eid).registry.landscape()
