"""Insight: read a system that nobody designed, and turn what is there into work.

Every other surface in this platform starts from signed intent. This one starts from the
opposite end — a live tenant that has been configured for years by people who have left, where
the design document either never existed or stopped being true in 2019. Brownfield is most of
the market, and "load your signed workbook" is not an answer to it.

The four services here are one pipeline, not four features:

  archaeology  reverses a live system into draft IR, **unsigned by construction**, so the drafts
               are unloadable (invariant 1) until a named human signs them. What the platform
               recovers is never mistaken for what somebody decided.
  debt         rides on the backlog rather than on a route of its own: it scores what archaeology
               found, from counters it can actually observe, and publishes which weights it did
               not measure.
  blast radius answers the question a steering committee actually asks — not "which objects does
               this touch" but "how many people, and which ones".
  time-travel  replays the ledger to any moment, because the ledger is the truth and "now" is
               just the last frame of it.

The connection to the rest of the platform is `sign`: a signed draft stops being archaeology and
becomes ordinary IR, which means the planner sequences it, documents project it, and verification
checks it — with no code here doing any of those things. That is the point. Archaeology is a
door into the existing machine, not a second machine.

Signing follows ADR-0015: the signature is written by the act from the authenticated caller, and
a caller-supplied signer is refused. A platform that lets you type someone else's name into a
signature field does not have signatures.
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from jidoka_core.ir import IRValidationError, load_ir
from jidoka_core.registry import RegistryError
from jidoka_insight.archaeology import reverse_ir, unexplained
from jidoka_insight.blast import blast_radius
from jidoka_insight.debt import measure
from jidoka_insight.timetravel import as_of
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/insight", tags=["insight"])


def _binding(e, system_id: str):
    """The connector this system is bound to, or the refusal that names what is missing."""
    try:
        rec = e.registry.get(system_id)
    except RegistryError as ex:
        raise HTTPException(404, str(ex))
    binding = e.connectors.get(system_id)
    if binding is None:
        raise HTTPException(409, f"{system_id} has no binding on this engagement. Bind a "
                                 f"connector before reading it — the platform does not read a "
                                 f"customer's system on an unauthorised path.")
    return rec, binding


def _draft_key(draft: dict) -> str:
    """Same shape as IRRecord.key, so a draft and the record it becomes are the same thing named
    the same way — in the backlog, in the ledger, and in the plan afterwards."""
    return f"{draft['product']}:{draft['object']}:{draft.get('external_code') or '?'}"


def _read(binding, rec, entities: list[str]) -> list[dict]:
    """Extract each entity and tag every row with the entity it came from.

    reverse_ir keys off `__entity`; without the tag every recovered object would be named
    "Unknown", which is a worse answer than refusing to read at all.
    """
    rows: list[dict] = []
    for entity in entities:
        try:
            found = binding.fetch(rec.system_id, entity)
        except Exception as ex:              # noqa: BLE001 — every connector raises its own type
            raise HTTPException(502, f"{rec.system_id}: reading {entity} failed "
                                     f"({type(ex).__name__}). The system was not changed.")
        rows += [{**row, "__entity": entity} for row in found]
    return rows


class DigIn(BaseModel):
    system_id: str
    entities: list[str]


@router.post("/archaeology")
def dig(eid: str, body: DigIn, identity: Identity = Depends(require("write_ir"))):
    """Reverse a live system into draft IR. Reads only — nothing is written to the tenant."""
    e = get_or_404(eid)
    if not body.entities:
        raise HTTPException(422, "Name at least one entity to read — archaeology does not guess "
                                 "what a system contains.")
    rec, binding = _binding(e, body.system_id)
    drafts = reverse_ir(_read(binding, rec, body.entities), rec.product, body.system_id)

    # A re-dig replaces this system's drafts and leaves other systems' alone: the live system is
    # the authority on what it currently contains, and a stale draft is a lie about a real tenant.
    e.drafts = [d for d in e.drafts if d["system_binding"] != body.system_id] + drafts
    e.persist_drafts()
    e.ledger.append(body.system_id, "ARCHAEOLOGY_RUN", identity.subject,
                    f"{len(drafts)} object(s) recovered from {body.system_id} across "
                    f"{len(body.entities)} entity set(s); unsigned and unexecutable until signed",
                    system=body.system_id, entities=list(body.entities), recovered=len(drafts))
    return _backlog(e)


def _backlog(e) -> dict:
    signed = {r.key for r in e.ir}
    drafts = [{**d, "key": _draft_key(d), "signed": _draft_key(d) in signed} for d in e.drafts]
    return {"drafts": drafts,
            "unexplained": unexplained(e.drafts),
            "systems": sorted({d["system_binding"] for d in e.drafts}),
            "debt": measure(e.drafts, list(e.decisions.dps.values()))}


@router.get("/archaeology")
def backlog(eid: str, identity: Identity = Depends(require("read"))):
    """What was recovered, what is still unexplained, and what that costs."""
    return _backlog(get_or_404(eid))


class SignIn(BaseModel):
    keys: list[str]
    workbook: str = ""
    rationale: str = ""


@router.post("/archaeology/sign")
def sign(eid: str, body: SignIn, identity: Identity = Depends(require("write_ir"))):
    """Sign recovered drafts into executable intent — the door from archaeology into the platform.

    The signer is the authenticated caller and nothing else (ADR-0015). Signed records go through
    `load_ir` and the number-range gate exactly as an uploaded workbook does: this is not a side
    entrance into IR, it is the front door with a different provenance written on it.
    """
    e = get_or_404(eid)
    wanted = set(body.keys)
    if not wanted:
        raise HTTPException(422, "Name the drafts to sign — signing everything recovered is how "
                                 "an unexamined tenant becomes unexamined intent.")
    chosen = [d for d in e.drafts if _draft_key(d) in wanted]
    missing = wanted - {_draft_key(d) for d in chosen}
    if missing:
        raise HTTPException(404, f"No recovered draft with key(s) {sorted(missing)}.")

    today = date.today().isoformat()
    signed_raw = []
    for d in chosen:
        raw = {k: v for k, v in d.items() if k not in ("provenance_status", "rationale")}
        raw["source"] = {**d["source"], "signed_by": identity.subject, "date": today,
                         "workbook": body.workbook or d["source"]["workbook"]}
        signed_raw.append(raw)

    try:
        loaded, open_dps = load_ir(signed_raw)
    except IRValidationError as ex:
        raise HTTPException(422, str(ex))
    clashes = [msg for r in loaded
               if (msg := e.numbering.validate(r.object, r.external_code
                                               or r.intent.get("externalCode")))]
    if clashes:
        raise HTTPException(422, "; ".join(clashes))

    # Signing replaces any record already holding the same key: a second reading of the same live
    # object is a correction, not a duplicate.
    keys = {r.key for r in loaded}
    e.ir = [r for r in e.ir if r.key not in keys] + loaded
    e.open_dps = {**e.open_dps, **open_dps}
    e.drafts = [d for d in e.drafts if _draft_key(d) not in keys]
    e.persist_ir()
    e.persist_drafts()
    for r in loaded:
        e.ledger.append(r.key, "IR_SIGNED", identity.subject,
                        f"recovered from {r.system_binding} and signed into executable intent"
                        + (f": {body.rationale}" if body.rationale else ""),
                        object=r.object, tier=r.tier, system=r.system_binding)
    return {"signed": sorted(keys), "open_dps": open_dps, "ir_records": len(e.ir),
            "backlog": _backlog(e)}


@router.get("/timetravel")
def timetravel(eid: str, at: str = Query(..., description="ISO timestamp to replay the ledger to"),
               identity: Identity = Depends(require("read"))):
    """Programme state as of a moment. Event sourcing: 'now' is only the last frame."""
    e = get_or_404(eid)
    state = as_of(e.ledger.entries, at)
    return {"at": at,
            "approved": sorted(state["approved"]),
            "rolled_back": sorted(state["rolled_back"]),
            "open_dps": sorted(state["open_dps"]),
            "halted": state["halted"],
            "entries": sum(1 for x in e.ledger.entries if x["ts"] <= at)}


class BlastIn(BaseModel):
    system_id: str
    entity: str
    selector: dict = {}
    delta: str = ""
    id_field: str = "userId"


@router.post("/blast")
def blast(eid: str, body: BlastIn, identity: Identity = Depends(require("read"))):
    """Who a change touches, counted in people rather than objects.

    The population is read live. A blast radius computed from a design document counts the people
    somebody meant to have; only the system knows who is actually in it.
    """
    e = get_or_404(eid)
    rec, binding = _binding(e, body.system_id)
    rows = _read(binding, rec, [body.entity])
    if rows and not any(body.id_field in r for r in rows):
        raise HTTPException(422, f"No row in {body.entity} carries {body.id_field!r}, so the "
                                 f"affected people cannot be named. Give the field that "
                                 f"identifies a person in this entity.")
    population = [{**r, "id": r.get(body.id_field)} for r in rows]
    return blast_radius({"selector": body.selector, "delta": body.delta}, population)

