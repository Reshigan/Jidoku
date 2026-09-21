"""The cross-module contract registry: one writer, declared readers.

A customisation is never module-local. The Komatsu lesson: `custom-string4` is written by EC and
read by Time Off eligibility, EE reporting and the ECC payroll interface — four surprises waiting
for a release if it is handled as a field, one declaration if it is handled as a contract.

This endpoint is a projection over signed intent. It stores nothing: the contract is part of the
record, so the registry cannot disagree with the design it describes.
"""
from fastapi import APIRouter, Depends
from jidoka_core.contracts import conflicts, registry, undeclared_readers

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/contracts", tags=["contracts"])


@router.get("")
def contracts(eid: str, identity: Identity = Depends(require("read"))):
    """Every contracted object, who owns it, who reads it — and who reads it without saying so."""
    e = get_or_404(eid)
    clash = conflicts(e.ir)
    return {"contracts": list(registry(e.ir).values()),
            "conflicts": [{"key": k, "says": v[0]} for k, v in sorted(clash.items())],
            "undeclared_readers": undeclared_readers(e.ir),
            "rule": ("One writer, declared readers. A second module wanting to write the same "
                     "object is a plan-blocking design decision, not a merge to resolve — and a "
                     "module reading an object it is not registered against is a dependency the "
                     "owner will break without knowing who it breaks.")}
