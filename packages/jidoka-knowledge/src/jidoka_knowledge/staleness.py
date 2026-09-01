"""Deterministic staleness. No model, no cost, so it can run on every read (ADR-0010).

Two kinds of evidence, two checks:
  - stored evidence (IR record, ledger entry): re-hash it, compare to source_hash
  - live SAP objects: the adapter's existing verify() already answers MATCH/DRIFT/MISSING

A stale claim is flagged, never deleted and never silently refreshed. The badge persists until
something re-verifies it against the source.
"""
from .claim import Claim, evidence_hash, TRUSTED, STALE, UNVERIFIED

DRIFTED = {"DRIFT", "MISSING"}


def recheck(claim: Claim, evidence) -> str:
    """Re-hash stored evidence and set the badge. evidence=None means the source is gone."""
    if evidence is None:
        claim.status = STALE
        return STALE
    claim.status = TRUSTED if evidence_hash(evidence) == claim.source_hash else STALE
    return claim.status


def recheck_live(claim: Claim, adapter, ir_record, live_state: list[dict]) -> str:
    """Ground a claim against a running system using the adapter contract that already exists.

    verify() returns a dict whose status is MATCH/DRIFT/MISSING; anything not MATCH means the
    world moved under the belief.
    """
    result = adapter.verify(ir_record, live_state)
    status = result.get("status") if isinstance(result, dict) else result
    claim.status = STALE if status in DRIFTED else TRUSTED
    return claim.status


def sweep(store, evidence_for) -> dict:
    """Recheck every open claim. evidence_for(claim) returns current evidence, or None if gone.

    Returns counts for the badge line the UI shows: how much of memory is still standing up.
    """
    counts = {TRUSTED: 0, STALE: 0, UNVERIFIED: 0}
    for claim in store.current():
        counts[recheck(claim, evidence_for(claim))] += 1
    return counts


def supersede(store, claim: Claim, text: str, evidence, source_ref: str, actor: str) -> Claim:
    """Correction in the flow of work: re-verify, then replace — closing the old interval.

    The prior claim is not deleted. It keeps its place in the chain with a closed interval, so
    the record of what was believed and when survives the correction.
    """
    fresh = Claim(subject=claim.subject, text=text, source_ref=source_ref,
                  source_hash=evidence_hash(evidence), actor=actor, supersedes=claim.id)
    fresh.status = TRUSTED
    return store.add(fresh)


class Unresolvable(Exception):
    """The source a claim names cannot be read back, so no comparison is possible."""


def resolve(claim: Claim, sources) -> object:
    """Read back the evidence a claim was formed from, by the scheme in its source_ref.

    A re-check is only deterministic if the evidence comes from the source rather than from the
    caller: a client that supplies its own evidence is answering the question it was asked to
    verify. So the caller names a resolver per scheme and the domain does the reading.

    Raises Unresolvable when no resolver claims the scheme, which is deliberately not the same
    answer as STALE — "the ground moved" and "nobody can see the ground" are different facts, and
    collapsing them makes an unreadable source look like a drifted one.
    """
    scheme = claim.source_ref.split(":", 1)[0]
    fn = sources.get(scheme)
    if fn is None:
        raise Unresolvable(f"nothing can read back a {scheme!r} source")
    return fn(claim.source_ref)
