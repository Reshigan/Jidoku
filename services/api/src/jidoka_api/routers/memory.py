"""Memory: this engagement's beliefs, and the gated path into shared knowledge (ADR-0010).

Every route here is scoped by {eid}. There is deliberately no route that reads across
engagements: cross-project reach is absent from the API rather than filtered out of it.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_knowledge import (Claim, SystemStore, evidence_hash, recheck, resolve, supersede,
                              promote, PromotionRefused, Unresolvable, STALE, TRUSTED, UNVERIFIED)
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
    return {"ir": read_ir}


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
    status = recheck(claim, evidence)
    e.persist_memory()          # the badge is part of the belief, not a view over it
    return {"status": status, "claim": _claim_out(claim)}


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
