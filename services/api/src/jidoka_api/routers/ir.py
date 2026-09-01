from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.ir import IRValidationError, load_ir
from jidoka_core.schema import IR_SCHEMA_VERSION, validate_against_schema

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/ir", tags=["ir"])


@router.post("")
def upload_ir(eid: str, records: list[dict], identity: Identity = Depends(require("write_ir"))):
    e = get_or_404(eid)
    try:
        e.ir, e.open_dps = load_ir(records)
    except IRValidationError as ex:
        raise HTTPException(422, str(ex))
    e.persist_ir()
    e.ledger.append("IR", "LOADED", identity.subject,
                    f"{len(e.ir)} records, {len(e.open_dps)} with open DPs")
    return {"records": len(e.ir), "open_decision_points": e.open_dps}


@router.post("/validate")
def validate_only(eid: str, records: list[dict], identity: Identity = Depends(require("read"))):
    """Schema pass that reports EVERY error at once — workbook feedback, not the load gate."""
    get_or_404(eid)
    errors = {}
    for i, raw in enumerate(records):
        found = validate_against_schema(raw)
        if found:
            errors[str(i)] = found
    return {"schema": IR_SCHEMA_VERSION, "records": len(records), "errors": errors,
            "loadable": not errors}


@router.get("")
def current_ir(eid: str, identity: Identity = Depends(require("read"))):
    e = get_or_404(eid)
    return {"schema": IR_SCHEMA_VERSION, "open_decision_points": e.open_dps,
            "records": [{"key": r.key, "object": r.object, "product": r.product, "tier": r.tier,
                         "system_binding": r.system_binding, "external_code": r.external_code,
                         "depends_on": r.depends_on, "intent": r.intent, "source": r.source}
                        for r in e.ir]}
