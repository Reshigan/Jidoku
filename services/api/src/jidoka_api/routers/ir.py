from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.decisions import DecisionPoint
from jidoka_core.delta import question as pool_question, state as pool_state
from jidoka_core.ir import IRValidationError, load_ir
from jidoka_core.schema import IR_SCHEMA_VERSION, validate_against_schema
from jidoka_core.supersede import diff, orphans, question

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/ir", tags=["ir"])


@router.post("")
def upload_ir(eid: str, records: list[dict], identity: Identity = Depends(require("write_ir"))):
    e = get_or_404(eid)
    try:
        loaded, open_dps = load_ir(records)
    except IRValidationError as ex:
        raise HTTPException(422, str(ex))
    # Codes are checked before anything is kept: an IR set that half-loads leaves the engagement
    # holding records whose codes the numbering registry would have refused.
    clashes = [msg for r in loaded
               if (msg := e.numbering.validate(r.object, r.external_code
                                               or r.intent.get("externalCode")))]
    if clashes:
        raise HTTPException(422, "; ".join(clashes))
    # What this version did to the last one, before the last one is gone. A design history that
    # cannot be read back is not a history (ADR-0039).
    had = list(e.ir)
    change = diff(had, loaded)
    stranded = orphans(change["removed"], e.ledger.entries)

    e.ir, e.open_dps = loaded, open_dps
    e.persist_ir()
    e.ledger.append("IR", "LOADED", identity.subject,
                    f"{len(e.ir)} records, {len(e.open_dps)} with open DPs")
    # Only where there was something to supersede. A first load adds every record and supersedes
    # nothing, and an entry saying otherwise would make the word mean less every time it appeared.
    if had and any(change[k] for k in ("added", "removed", "changed")):
        e.ledger.append("IR", "SUPERSEDED", identity.subject,
                        f"{len(change['added'])} added, {len(change['removed'])} removed, "
                        f"{len(change['changed'])} changed, {len(change['unchanged'])} unchanged",
                        **{k: change[k] for k in ("added", "removed", "changed")})

    # A record the new design dropped that a customer's system is still holding. Drift's sibling,
    # and it gets drift's treatment: two exits, and planning halts until a person picks one.
    for orphan in stranded:
        dp_id = f"DP-ORPHAN-{orphan['key']}"
        if dp_id not in e.decisions.dps:
            e.decisions.raise_dp(DecisionPoint(
                dp_id=dp_id, dp_type="DESIGN", question=question(orphan),
                owner="whoever signs this engagement's design",
                options=["re-sign it into the design", "take it out of the system"]))
        e.ledger.append(orphan["key"], "ORPHANED", identity.subject, orphan["says"],
                        last=orphan["last"])

    # The delta pool (ADR-0041). Counted from the design, so the commercial question is asked
    # when somebody proposes the thirty-first — not after it has reached a tenant.
    pool = pool_state(e.ir, e.ledger.entries)
    if pool["over"] and "DP-DELTA-POOL" not in e.decisions.dps:
        e.decisions.raise_dp(DecisionPoint(
            dp_id="DP-DELTA-POOL", dp_type="COMMERCIAL",
            question=pool_question(pool["over"], pool["of"]),
            owner="whoever signed the delta pool",
            options=["extend the pool", "drop the extra customisations",
                     "take them back to the delivered standard"]))
        e.ledger.append("DELTA", "POOL_EXHAUSTED", identity.subject, pool["says"],
                        over=pool["over"], of=pool["of"])

    return {"records": len(e.ir), "open_decision_points": e.open_dps,
            "superseded": change, "orphaned": stranded, "delta_pool": pool}


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
