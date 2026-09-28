"""Intent an agent drafted, waiting for a person.

The agent may write a draft. It may not sign one, and there is nowhere in a draft for a signature to
be written: a proposal arrives with `source.signed_by` empty and is refused if it arrives with one.
Signing is `approve`, the signer must not be the proposer, the signature is stamped from the
authenticated identity rather than from anything in the request body, and the signed record goes
through `load_records` — the same gates a workbook upload passes — merged into the design rather than
replacing it (`POST /ir` replaces, which is right for a workbook and wrong for one record).

Nothing here stores anything. A proposal is an `IR_PROPOSED` entry carrying the record, and its state
is a projection over the chain, so it survives a restart and cannot disagree with what happened.
"""
import dataclasses
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from jidoka_core import proposals
from jidoka_core.ir import validate_record
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404
from .ir import _honest_tier, load_records

router = APIRouter(prefix="/engagements/{eid}/proposals", tags=["proposals"])


class Draft(BaseModel):
    records: list[dict]
    #: What the drafter says it did not do. Kept on the chain beside the drafts: a pass that silently
    #: skipped a scope item is worse than one that said so.
    note: str = ""


class Reason(BaseModel):
    reason: str = ""


def _find(e, key: str) -> dict:
    row = next((r for r in proposals.state(e.ledger.entries) if r["key"] == key), None)
    if row is None:
        raise HTTPException(404, f"{key!r} has not been proposed on this engagement.")
    return row


@router.post("")
def propose(eid: str, body: Draft, identity: Identity = Depends(require("write_ir"))):
    """Take drafts. Every record is checked whole before any is kept: a batch that half-lands leaves
    a reviewer reading proposals from a pass that was refused."""
    e = get_or_404(eid)
    problems: dict[str, list[str]] = {}
    for i, raw in enumerate(body.records):
        found = proposals.check(raw)
        if not found:                       # `check` passing means it is a dict that validates
            rec, _ = validate_record(proposals.for_validation(raw))
            honest = _honest_tier(rec)
            if honest is None and rec.tier == "A":
                found = [f"{rec.object!r} is tier A and the {rec.product} adapter does not know it."]
            elif honest is not None and honest != rec.tier:
                found = [f"tier {rec.tier} claimed; the {rec.product} adapter declares "
                         f"{rec.object!r} as tier {honest}."]
        if found:
            problems[str(i)] = found
    if problems:
        raise HTTPException(422, "; ".join(f"record {i}: {' '.join(p)}"
                                           for i, p in problems.items()))

    keys = []
    for raw in body.records:
        key = proposals.key_of(raw)
        e.ledger.append(key, proposals.PROPOSED, identity.subject,
                        body.note or (raw.get("source") or {}).get("workbook", ""), record=raw)
        keys.append(key)
    return {"proposed": keys, "awaiting_a_signature": len(keys),
            "says": f"{len(keys)} draft(s) recorded. None is intent until a person signs it."}


@router.get("")
def listing(eid: str, identity: Identity = Depends(require("read"))):
    e = get_or_404(eid)
    rows = proposals.state(e.ledger.entries)
    return {"proposals": rows,
            "pending": sum(1 for r in rows if r["status"] == "pending"),
            "signed": sum(1 for r in rows if r["status"] == "signed"),
            "rejected": sum(1 for r in rows if r["status"] == "rejected")}


@router.post("/{key:path}/sign")
def sign(eid: str, key: str, identity: Identity = Depends(require("approve"))):
    """A person makes a draft intent. `approve`, because that is what signing is."""
    e = get_or_404(eid)
    row = _find(e, key)
    if row["status"] != "pending":
        raise HTTPException(409, f"{key} is already {row['status']}.")
    if identity.subject == row["proposed_by"]:
        raise HTTPException(
            409, f"{identity.subject} proposed {key} and may not sign it. Whoever drafts a record "
                 f"and whoever makes it intent are two people (invariant 4).")

    signed = proposals.sign(row["record"], identity.subject,
                            datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    # Merged, never replacing: the design as it stands, with this record added or revised.
    others = [dataclasses.asdict(r) for r in e.ir if r.key != key]
    result = load_records(e, [*others, signed], identity)
    e.ledger.append(key, proposals.SIGNED, identity.subject, f"signed by {identity.subject}")
    return {"signed": key, "signed_by": identity.subject, "design": result}


@router.post("/{key:path}/reject")
def reject(eid: str, key: str, body: Reason, identity: Identity = Depends(require("approve"))):
    """Decline a draft, with a reason. The drafter can propose again; the rejection stays."""
    e = get_or_404(eid)
    row = _find(e, key)
    if row["status"] != "pending":
        raise HTTPException(409, f"{key} is already {row['status']}.")
    if not body.reason.strip():
        raise HTTPException(422, "A rejection says why. The drafter reads it to fix the record, and "
                                 "an auditor reads it to see what a signature was withheld for.")
    e.ledger.append(key, proposals.REJECTED, identity.subject, body.reason.strip())
    return {"rejected": key, "reason": body.reason.strip()}
