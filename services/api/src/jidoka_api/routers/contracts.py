"""The cross-module contract registry: one writer, declared readers.

A customisation is never module-local. The Komatsu lesson: `custom-string4` is written by EC and
read by Time Off eligibility, EE reporting and the ECC payroll interface — four surprises waiting
for a release if it is handled as a field, one declaration if it is handled as a contract.

This endpoint is a projection over signed intent. It stores nothing: the contract is part of the
record, so the registry cannot disagree with the design it describes.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.contracts import conflicts, registry, undeclared_readers
from jidoka_core.delta import DEFAULT_POOL, SIZE_ACTION, state as pool_state

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/contracts", tags=["contracts"])


@router.post("/pool")
def set_pool(eid: str, size: int = DEFAULT_POOL,
             identity: Identity = Depends(require("approve"))):
    """How many customisations this engagement bought. A commercial fact, so it takes `approve`:
    the number is somebody's agreement and the platform is never the one who changes it."""
    e = get_or_404(eid)
    if size < 0 or size > 10_000:
        raise HTTPException(422, "A delta pool is a number somebody agreed to, between 0 and "
                                 "10000. Outside that it is not a budget.")
    e.ledger.append("DELTA", SIZE_ACTION, identity.subject,
                    f"this engagement's delta pool is {size}", size=size)
    return pool_state(e.ir, e.ledger.entries)


@router.get("")
def contracts(eid: str, identity: Identity = Depends(require("read"))):
    """Every contracted object, who owns it, who reads it — and who reads it without saying so."""
    e = get_or_404(eid)
    clash = conflicts(e.ir)
    return {"contracts": list(registry(e.ir).values()),
            "conflicts": [{"key": k, "says": v[0]} for k, v in sorted(clash.items())],
            "undeclared_readers": undeclared_readers(e.ir),
            "delta_pool": pool_state(e.ir, e.ledger.entries),
            "rule": ("One writer, declared readers. A second module wanting to write the same "
                     "object is a plan-blocking design decision, not a merge to resolve — and a "
                     "module reading an object it is not registered against is a dependency the "
                     "owner will break without knowing who it breaks.")}
