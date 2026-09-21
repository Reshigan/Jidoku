"""The type-check over signed intent: what does not hold, and the authority that says so.

C1 (ADR-0036). The planner refuses on a type error, which is the gate; this is the same check run
for reading rather than for blocking, so a designer can see every failure at once instead of
discovering them one refusal at a time.

Every message here is the auditor's control narrative verbatim. A rejection that needed
translating before it could go in a report would be translated by hand, once, and then drift.
"""
from fastapi import APIRouter, Depends
from jidoka_core.refinements import KINDS, check, missing_required

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/types", tags=["types"])


@router.get("")
def types(eid: str, identity: Identity = Depends(require("read"))):
    """Every refinement that does not hold, and every required field that is empty."""
    e = get_or_404(eid)
    disagrees, absent = check(e.ir), missing_required(e.ir)
    return {"disagrees": disagrees, "absent": absent,
            "holds": not (disagrees or absent),
            "kinds": list(KINDS),
            "method": ("A refinement is a constraint carried by the value itself. A statutory "
                       "bound cites the statute, the person who signed it and the date — a "
                       "ceiling somebody typed in is an opinion. A dependent value is decided by "
                       "another object's field, because writing the same fact twice is how they "
                       "come to disagree. A required field is one every schema accepts empty and "
                       "that is wrong in a way nobody sees until the first run that needs it.")}
