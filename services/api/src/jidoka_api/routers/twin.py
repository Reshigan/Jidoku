"""The twin: predict what the live system will do, then let the system grade the prediction.

A twin is worth believing only if it publishes how often it is right, so nothing here blocks
anything. A prediction is a model's opinion; a platform whose thesis is that assertion must be
impossible does not let an opinion stop a signed, armed, snapshotted write. The prediction goes on
the chain, the write proceeds through its own gates, and `fidelity` pairs the two afterwards
(ADR-0026).

Metadata is read from the bound connector rather than uploaded: the system's own service
definition is the primary source (ADR-0012), and a twin calibrated against a hand-supplied schema
would be measuring somebody's typing.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.twin import RuleTwin, fidelity, parse_rules
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/twin", tags=["twin"])


class RuleExport(BaseModel):
    rules: list[dict]
    source: str = ""


def _metadata_for(e, system_id: str) -> dict:
    """The shape SchemaTwin expects, parsed from the system's own $metadata."""
    from jidoka_adapters.successfactors.odata import parse_metadata

    binding = e.connectors.get(system_id)
    if binding is None or binding.metadata_xml is None:
        raise HTTPException(
            409, f"{system_id} has no binding that can read its service definition. A twin built "
                 f"without the system's own metadata would be measuring somebody's typing.")
    return parse_metadata(binding.metadata_xml())


@router.post("/rules")
def load_rules(eid: str, body: RuleExport, identity: Identity = Depends(require("write_ir"))):
    """Take a rule export. Rules outside the evaluatable subset are refused by name and kept in
    the record — a twin that silently skipped the hard rules would report high fidelity on the
    easy ones."""
    e = get_or_404(eid)
    rules, refused = parse_rules(body.rules)
    e.rules = [dict(r) for r in body.rules]
    e.persist_rules()
    e.ledger.append("TWIN", "RULES_LOADED", identity.subject,
                    f"{len(rules)} rule(s) evaluatable, {len(refused)} refused"
                    + (f" from {body.source}" if body.source else ""),
                    evaluatable=len(rules), refused=len(refused))
    return {"evaluatable": len(rules), "refused": refused,
            "rules": [{"rule_id": r.rule_id, "entity": r.entity, "source": r.source}
                      for r in rules]}


@router.post("")
def run_twin(eid: str, identity: Identity = Depends(require("ledger_append"))):
    """Predict the substrate's verdict for every record whose system can be read.

    Ledgers one TWIN_PREDICTED per record, which is what the fidelity projection later pairs with
    what the substrate actually did.
    """
    e = get_or_404(eid)
    rules, refused = parse_rules(e.rules)
    twins, predictions, skipped = {}, [], []
    for r in e.ir:
        if r.system_binding not in twins:
            try:
                twins[r.system_binding] = RuleTwin(_metadata_for(e, r.system_binding), rules)
            except HTTPException as ex:
                twins[r.system_binding] = None
                skipped.append({"key": r.key, "reason": ex.detail})
        twin = twins[r.system_binding]
        if twin is None:
            if not any(s["key"] == r.key for s in skipped):
                skipped.append({"key": r.key, "reason": f"no readable binding on {r.system_binding}"})
            continue
        out = twin.predict(r.object, r.intent)
        e.ledger.append(r.key, "TWIN_PREDICTED", identity.subject,
                        f"{out['verdict']}: " + ("; ".join(out["reasons"]) or "nothing objects"),
                        verdict=out["verdict"], reasons=out["reasons"],
                        rules_applied=out["rules_applied"])
        predictions.append({"key": r.key, **out})
    return {"predictions": predictions, "skipped": skipped, "refused_rules": refused,
            "rules_evaluatable": len(rules), "fidelity": fidelity(e.ledger.entries)}


@router.get("")
def twin_state(eid: str, identity: Identity = Depends(require("read"))):
    """What the twin has predicted and how often it has been right. A read of the chain."""
    e = get_or_404(eid)
    rules, refused = parse_rules(e.rules)
    last = {x.get("task"): x for x in e.ledger.entries if x.get("action") == "TWIN_PREDICTED"}
    return {"predictions": [{"key": k, "verdict": x.get("verdict"), "reasons": x.get("reasons", []),
                             "at": x.get("ts")} for k, x in sorted(last.items())],
            "rules_evaluatable": len(rules), "refused_rules": refused,
            "fidelity": fidelity(e.ledger.entries)}
