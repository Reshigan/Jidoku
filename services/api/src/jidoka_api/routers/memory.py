"""Memory: this engagement's beliefs, and the gated path into shared knowledge (ADR-0010).

Every route here is scoped by {eid}. There is deliberately no route that reads across
engagements: cross-project reach is absent from the API rather than filtered out of it.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_knowledge import (Claim, SystemStore, evidence_hash, recheck, resolve, supersede,
                              promote, PromotionRefused, Unresolvable, STALE, TRUSTED, UNVERIFIED,
                              harvest, from_tier_map, promotable, row_of,
                              STRUCTURE_SOURCES, SETTING_SOURCES)
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/memory", tags=["memory"])

# Cross-project memory: what JIDOKA knows about SAP, never about a client. One per process;
# only the scrubber gate writes it.
SYSTEM_MEMORY = SystemStore()


def _claim_out(c: Claim) -> dict:
    return {"id": c.id, "subject": c.subject, "text": c.text, "status": c.status,
            "source_ref": c.source_ref, "confidence": c.confidence, "actor": c.actor,
            "valid_from": c.valid_from, "valid_to": c.valid_to, "supersedes": c.supersedes}


@router.get("")
def list_memory(eid: str, subject: str | None = None, identity: Identity = Depends(require("read"))):
    """Current beliefs plus the staleness counts the console badges its memory panel with."""
    e = get_or_404(eid)
    current = e.memory.current(subject)
    counts = {TRUSTED: 0, STALE: 0, UNVERIFIED: 0}
    for c in current:
        counts[c.status] = counts.get(c.status, 0) + 1
    return {"project": [_claim_out(c) for c in current],
            "system": [_claim_out(c) for c in SYSTEM_MEMORY.current(subject)],
            "counts": counts,
            "stale": [_claim_out(c) for c in e.memory.stale()]}


@router.get("/as-of")
def memory_as_of(eid: str, when: str, identity: Identity = Depends(require("read"))):
    """What was believed at a point in time. Validity intervals make this free."""
    e = get_or_404(eid)
    return {"as_of": when, "claims": [_claim_out(c) for c in e.memory.as_of(when)]}


class ClaimIn(BaseModel):
    subject: str
    text: str
    source_ref: str
    evidence: dict | list | str
    confidence: float = 1.0


@router.post("")
def form_claim(eid: str, body: ClaimIn, identity: Identity = Depends(require("write_ir"))):
    """Form a grounded belief. An ungrounded claim is refused by the domain, not by this route."""
    e = get_or_404(eid)
    try:
        claim = e.memory.add(Claim(body.subject, body.text, body.source_ref,
                                   evidence_hash(body.evidence), identity.subject,
                                   confidence=body.confidence))
    except ValueError as ex:
        raise HTTPException(422, str(ex))
    e.persist_memory()
    return _claim_out(claim)


def _sources(e) -> dict:
    """Readers that can fetch a claim's evidence back, keyed by the scheme in its source_ref.

    Deliberately server-side. If the caller supplied the evidence, a re-check would be answering
    the question it was asked to verify, and every claim would report whatever the client said.
    Only schemes backed by something the platform actually holds appear here.
    """
    def read_ir(ref: str):
        """ir:<object> or ir:<system>:<object>, read out of the engagement's own signed intent.

        Returns None when the object is no longer in intent. That is the same answer as "the
        source is gone", and here the two genuinely coincide: intent is the source, so an object
        absent from it has no ground left to compare against.
        """
        parts = ref.split(":")
        system, name = (parts[1], parts[2]) if len(parts) > 2 else (None, parts[1])
        for r in e.ir:
            if r.object == name and (system is None or r.system_binding == system):
                return {"object": r.object, "system_binding": r.system_binding,
                        "intent": r.intent, "tier": r.tier}
        return None

    def read_harvest(ref: str):
        """harvest:<system_id>:<entity> — re-read through the same binding the claim was formed on.

        Re-reading through the same adapter is what makes staleness a comparison rather than a
        fresh opinion. The claim's hash is over one row, so the entity read is narrowed back to
        the row it came from; a row that is no longer there reads as gone, which is STALE.
        """
        _, system_id, entity = ref.split(":", 2)
        binding = e.connectors.get(system_id)
        if binding is None:
            raise Unresolvable(
                f"{system_id} has no binding on this engagement — nothing can read it back.")
        try:
            rec = e.registry.get(system_id)
        except Exception as ex:
            raise Unresolvable(str(ex))
        rows = _harvest_rows(_adapter(rec, binding), rec, binding, entity)
        return rows

    return {"ir": read_ir, "harvest": read_harvest}


def _adapter(rec, binding):
    """The product's adapter, reading through this binding. Unknown product is a refusal."""
    from jidoka_adapters import ADAPTERS
    if rec.product not in ADAPTERS:
        raise HTTPException(422, f"No adapter registered for product {rec.product!r}. "
                                 f"Known products: {sorted(ADAPTERS)}.")
    return ADAPTERS[rec.product](fetch=binding.fetch)


def _harvest_rows(adapter, rec, binding, entity: str):
    """Rows for one metadata entity, read from the system's own service definition.

    The service definition is the source (ADR-0012), so it is parsed here rather than served from
    the connector's data collections — those hold rows a tenant put in, not the shape they may
    take. A binding with no metadata reader has nothing structural to offer and says so.
    """
    from jidoka_knowledge import metadata as md
    if entity == "tiers":
        # A tier declaration is the adapter's own binding statement about the product, not
        # anything the service definition publishes. Its ground is the tier_map, so that is what
        # a re-check has to compare against.
        return [{"object": o, "tier": t} for o, t in sorted((adapter.tier_map() or {}).items())]
    if binding.metadata_xml is None:
        raise Unresolvable(f"{rec.system_id}'s binding cannot read a service definition.")
    # The service definition names its value sets; the value-set collection says what is in them.
    # Without the second read a domain claim can only say "constrained", which is the fact the
    # consultant already knew. With it, the claim carries the permitted values themselves.
    try:
        picklists = binding.fetch(rec, "PicklistV2")
    except Exception:
        # ponytail: every connector raises its own error type and the right answer to all of them
        # is the same — form the structural claims without the values rather than none at all.
        picklists = None
    fetch = md.read(binding.metadata_xml(), picklists=picklists)
    try:
        return fetch(rec, entity)
    except KeyError:
        return []


@router.post("/{claim_id}/recheck")
def recheck_claim(eid: str, claim_id: str, identity: Identity = Depends(require("read"))):
    """Deterministic re-check: the server re-reads the source and compares hashes. No model call.

    Takes no evidence from the caller by design. A source nobody can read back is reported as
    such (409) rather than as drift — an unreadable source and a moved one are different facts.
    """
    e = get_or_404(eid)
    claim = e.memory.get(claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    try:
        evidence = resolve(claim, _sources(e))
    except Unresolvable as ex:
        raise HTTPException(409, str(ex))
    if claim.source_ref.startswith("harvest:"):
        # A harvest resolver reads an entity; the claim was formed from one row inside it. Match
        # by hash rather than by key so no product's key fields have to be known here — and a row
        # that changed is correctly not found, which is the same answer as gone.
        evidence = row_of(claim, evidence)
    status = recheck(claim, evidence)
    e.persist_memory()          # the badge is part of the belief, not a view over it
    return {"status": status, "claim": _claim_out(claim)}


class HarvestIn(BaseModel):
    system_id: str


@router.post("/harvest")
def harvest_system(eid: str, body: HarvestIn, identity: Identity = Depends(require("write_ir"))):
    """Learn a registered system from its own metadata (ADR-0012).

    Read-only by construction: the adapter's extract() is the only method this path can reach, and
    a read-only binding has no write half at all. Nothing is promoted here — `offered` is the queue
    a named human takes through the scrubber gate, which is the whole point of it being separate.
    """
    e = get_or_404(eid)
    try:
        rec = e.registry.get(body.system_id)
    except Exception as ex:
        raise HTTPException(404, str(ex))
    binding = e.connectors.get(body.system_id)
    if binding is None:
        raise HTTPException(409, f"{body.system_id} has no binding on this engagement. "
                                 f"Bind a connector before harvesting it.")
    adapter = _adapter(rec, binding)

    class _Reader:
        """The adapter's fetch slot, backed by the system's service definition rather than by its
        data collections. Structure is what a harvest is for."""
        def __init__(self, inner):
            self._inner = inner
        def extract(self, system, entity):
            return _harvest_rows(self._inner, rec, binding, entity)
        def tier_map(self):
            return self._inner.tier_map()

    try:
        # tiers is excluded here and formed by from_tier_map instead: both would say the same
        # thing, and the same fact believed twice is two things to keep in step.
        sources = tuple(s for s in STRUCTURE_SOURCES + SETTING_SOURCES if s != "tiers")
        formed = harvest(_Reader(adapter), rec, e.memory, identity.subject, sources=sources)
        formed += from_tier_map(adapter, rec, e.memory, identity.subject)
    except Unresolvable as ex:
        raise HTTPException(409, str(ex))
    e.persist_memory()
    offered = promotable(formed)
    return {"system_id": body.system_id, "formed": len(formed),
            "offered": [_claim_out(c) for c in offered],
            "claims": [_claim_out(c) for c in formed]}


class CorrectIn(BaseModel):
    text: str
    source_ref: str
    evidence: dict | list | str


@router.post("/{claim_id}/correct")
def correct_claim(eid: str, claim_id: str, body: CorrectIn,
                  identity: Identity = Depends(require("write_ir"))):
    """Correction in the flow of work: supersede, never overwrite. The prior belief survives."""
    e = get_or_404(eid)
    claim = e.memory.get(claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    if not claim.open:
        raise HTTPException(409, "claim is already superseded; correct the current one instead")
    fresh = supersede(e.memory, claim, body.text, body.evidence, body.source_ref, identity.subject)
    e.persist_memory()
    return {"superseded": claim_id, "claim": _claim_out(fresh)}


class PromoteIn(BaseModel):
    approver: str


@router.post("/{claim_id}/promote")
def promote_claim(eid: str, claim_id: str, body: PromoteIn,
                  identity: Identity = Depends(require("approve"))):
    """The scrubber gate — the only flow that crosses a tenant boundary.

    Requires approve authority AND a named approver distinct from the claim's builder. Client
    values are refused rather than redacted: a silently stripped sentence is one the approver
    never actually read.
    """
    e = get_or_404(eid)
    claim = e.memory.get(claim_id)
    if claim is None:
        raise HTTPException(404, "claim not found")
    try:
        promoted = promote(claim, SYSTEM_MEMORY, body.approver, claim.actor, ledger=e.ledger)
    except PromotionRefused as ex:
        raise HTTPException(422, str(ex))
    return {"promoted": _claim_out(promoted)}
