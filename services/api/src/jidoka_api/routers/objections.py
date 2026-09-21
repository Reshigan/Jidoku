"""Objections: stated once, overridden by a named person, revisited where the consequence lands.

The auditor in the crew has objected since ADR-0018, onto an in-memory bus that the run reported
and then dropped. So the platform disagreed, nobody could record having overruled it, and nothing
ever went back to see what happened — which is the one part of M6 that costs anything and the only
part that makes the next objection worth hearing.

Nothing here blocks. An objection is not a gate: the gates are the seven invariants and they
refuse. This is the platform disagreeing with a decision it has no standing to prevent, and
dressing that as a gate would be the platform voting.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.objections import (GROUNDS, OVERRIDDEN, RAISED, REVISITED, WITHDRAWN, Objection,
                                    due, state, what_happened)
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/objections", tags=["objections"])


class OverrideIn(BaseModel):
    #: A person, never a role and never "the client". An override nobody signed is the platform
    #: being overruled by the weather.
    decided_by: str
    reason: str


def raise_once(e, o: Objection, actor: str) -> dict:
    """State it once. A second raising is the same objection, still open, and the chain records
    that it was restated without the reader being told about it twice."""
    oid = o.objection_id
    standing = state(e.ledger.entries).get(oid)
    entry = e.ledger.append(oid, RAISED, actor, o.finding, **o.as_entry())
    return {"objection_id": oid, "already_open": bool(standing and standing["status"] == "open"),
            "ts": entry["ts"]}


@router.post("/{oid}/override")
def override(eid: str, oid: str, body: OverrideIn,
             identity: Identity = Depends(require("approve"))):
    """Set an objection aside, under a name. Requires `approve`: overruling the platform's stated
    position is a decision, and the platform is never the one who makes it (invariant 7)."""
    e = get_or_404(eid)
    standing = state(e.ledger.entries).get(oid)
    if not standing:
        raise HTTPException(404, f"No objection {oid} on this chain.")
    if standing["status"] != "open":
        raise HTTPException(409, f"{oid} is {standing['status']}, not open.")
    if not body.decided_by.strip() or not body.reason.strip():
        raise HTTPException(422, "An override carries the name of the person who made it and "
                                 "their reason. An override nobody signed is the platform being "
                                 "overruled by the weather.")
    e.ledger.append(oid, OVERRIDDEN, body.decided_by, body.reason, deferred_by=identity.subject)
    return {"objection_id": oid, "status": "overridden", "decided_by": body.decided_by,
            "revisit_at": standing["revisit_at"]}


def withdraw_what_no_longer_holds(e, still_found: set, actor: str) -> list:
    """The platform conceding, on its own evidence rather than on a button.

    The objector re-states everything it still finds on every run, so an objection left open that
    it did not restate is one whose finding no longer holds. Withdrawal goes on the chain beside
    the objection, so a reader sees both — without it the only exits were being overruled or being
    right, and a platform with no way to concede is one nobody argues with honestly.
    """
    gone = []
    for oid, row in state(e.ledger.entries).items():
        if row["status"] == "open" and oid not in still_found:
            e.ledger.append(oid, WITHDRAWN, actor, "the finding no longer holds")
            gone.append(oid)
    return gone


@router.post("/{oid}/revisit")
def revisit(eid: str, oid: str, identity: Identity = Depends(require("ledger_append"))):
    """Close the loop: record that it was revisited, and report what the chain says happened.

    The report is not a verdict. "The objection was right" is a claim about a world where the
    override did not happen, and nothing here can see that world.
    """
    e = get_or_404(eid)
    standing = state(e.ledger.entries).get(oid)
    if not standing:
        raise HTTPException(404, f"No objection {oid} on this chain.")
    if standing["status"] != "overridden":
        raise HTTPException(409, f"{oid} is {standing['status']}. Only an objection somebody set "
                                 f"aside has a consequence to come back to.")
    outcome = what_happened(e.ledger.entries, standing["about"])
    e.ledger.append(oid, REVISITED, identity.subject, outcome["says"])
    return {"objection_id": oid, "status": "revisited", **outcome,
            "objection_said": standing["consequence"],
            "overridden_by": standing["overridden_by"]}


@router.get("")
def objections(eid: str, identity: Identity = Depends(require("read"))):
    """Everything this chain has objected to, and where each one stands."""
    e = get_or_404(eid)
    rows = list(state(e.ledger.entries).values())
    for row in rows:
        if row["status"] in ("overridden", "revisited"):
            row["what_happened"] = what_happened(e.ledger.entries, row["about"])["says"]
    return {"objections": rows,
            "open": [r for r in rows if r["status"] == "open"],
            "due_for_revisit": due(e.ledger.entries, e.phase),
            "phase": e.phase,
            "grounds": list(GROUNDS)}
