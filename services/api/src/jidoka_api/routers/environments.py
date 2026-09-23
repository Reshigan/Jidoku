"""Two registered systems, read and compared — the cutover question, asked.

Reading only, through the read-only binding: `build_reader` gives a connector whose `apply`
refuses, so invariant 3 holds by the shape of the object rather than by this module remembering
not to write. A comparison that could write would be an execute wearing a lab coat, exactly as
verification would be.

What is compared is what the engagement designed: the entities its signed intent touches. Not the
adapter's whole tier map — a diff of every object a product publishes is a report nobody reads,
and the objects a programme actually configured are the ones a cutover is about.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.environments import compare, roll_up
from jidoka_core.ir import record_key

from ..auth import Identity, require
from .engagements import get_or_404
from .execution import _adapter_for

router = APIRouter(prefix="/engagements/{eid}/environments", tags=["environments"])


def _system_or_422(e, system_id: str):
    try:
        return e.registry.get(system_id)
    except Exception:                        # noqa: BLE001 — an unregistered system is a 422
        raise HTTPException(422, f"{system_id} is not registered on this engagement. A system the "
                                 f"landscape does not know is a system nothing may read.") from None


@router.get("/compare")
def compare_environments(eid: str, left: str, right: str,
                         identity: Identity = Depends(require("read"))):
    """Read the same objects from two systems and report where they are not the same."""
    e = get_or_404(eid)
    if left == right:
        raise HTTPException(422, "A system compared with itself is always aligned, which is true "
                                 "and useless. Name two.")
    a, b = _system_or_422(e, left), _system_or_422(e, right)
    if a.product != b.product:
        raise HTTPException(422, f"{left} is {a.product} and {right} is {b.product}. Two products "
                                 f"do not hold the same objects, and a diff between them would "
                                 f"report every object as missing from one side.")

    ca, cb = e.connectors.get(left), e.connectors.get(right)
    missing = [s for s, c in ((left, ca), (right, cb)) if c is None]
    if missing:
        raise HTTPException(
            409, f"No connector is bound to {', '.join(missing)}. Nothing can be read from a "
                 f"system nothing is connected to. A comparison only reads, so the binding it "
                 f"wants is a reader — POST /execution/connector/reader, which takes the product "
                 f"from the registry and has no write half at all. The system being compared is "
                 f"usually one no IR record binds to, which is the point: the design names DEV "
                 f"and the question is about PROD.")

    # entity -> the signed intent for each key of it, so a difference can be weighed against the
    # design rather than only against the other environment.
    intents: dict[str, dict] = {}
    for r in e.ir:
        intents.setdefault(r.object, {})[record_key(r)] = dict(r.intent)

    adapter_a, adapter_b = _adapter_for(a.product, ca), _adapter_for(b.product, cb)
    out, unreadable = [], []
    for entity in sorted({r.object for r in e.ir}):
        if not adapter_a.verifiable(entity):
            unreadable.append({"entity": entity,
                               "reason": adapter_a.unverifiable().get(entity, "no read path")})
            continue
        key = getattr(adapter_a, "key_field", lambda _e: "externalCode")(entity)
        # Keys here are the entity's own; intent is keyed by IR record key, so match on the value.
        signed = {row.get(key): body for body, row in
                  ((v, v) for v in intents.get(entity, {}).values()) if row.get(key)}
        try:
            rows_a = adapter_a.extract(a, entity)
            rows_b = adapter_b.extract(b, entity)
        except Exception as ex:               # noqa: BLE001 — one unreadable entity is not the run
            unreadable.append({"entity": entity, "reason": type(ex).__name__})
            continue
        out.append({"entity": entity,
                    **compare(rows_a, rows_b, key, left, right, intent=signed)})

    return {**roll_up(out), "unreadable": unreadable,
            "method": ("Only the entities this engagement's signed intent touches, read from both "
                       "systems through bindings that cannot write. Neither side is treated as "
                       "the baseline: which one is right is a question about why they differ.")}
