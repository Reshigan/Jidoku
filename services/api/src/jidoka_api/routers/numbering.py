"""Number ranges: codes as governed allocations.

Registering a range and allocating a code both change what the engagement will accept, so both
are builder acts gated on write_ir — the same permission that loads the IR the codes end up in.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.numbering import NumberRange, NumberingError
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/numbering", tags=["numbering"])


class Range(BaseModel):
    range_id: str
    object_type: str
    prefix: str
    start: int
    end: int
    width: int = 4


class Allocation(BaseModel):
    object_type: str
    code: str | None = None


@router.get("")
def snapshot(eid: str, identity: Identity = Depends(require("read"))):
    return get_or_404(eid).numbering.snapshot()


@router.post("/ranges")
def register(eid: str, body: Range, identity: Identity = Depends(require("write_ir"))):
    e = get_or_404(eid)
    try:
        rng = e.numbering.register(NumberRange(**body.model_dump()), identity.subject)
    except NumberingError as ex:
        raise HTTPException(422, str(ex))
    return {"registered": rng.range_id, "governs": rng.object_type,
            "codes": f"{rng.format(rng.start)}..{rng.format(rng.end)}"}


@router.post("/allocate")
def allocate(eid: str, body: Allocation, identity: Identity = Depends(require("write_ir"))):
    e = get_or_404(eid)
    try:
        code = e.numbering.allocate(body.object_type, identity.subject, code=body.code)
    except NumberingError as ex:
        # A collision is a refusal with a name in it, not a server fault.
        raise HTTPException(409, str(ex))
    return {"allocated": code, "object_type": body.object_type}
