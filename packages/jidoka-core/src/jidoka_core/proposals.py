"""Intent an agent drafted, and the one act that makes it intent: a person signing it.

Invariant 1 says unsigned intent is unloadable. `validate_record` enforces that by checking
`source.signed_by` is *present* — which is a check on a field, not on an act. Fine while every record
came from a workbook a person had signed. It stops being fine the moment an agent authors records,
because a model can write any name into that field and pass the gate, and a record carrying a
signature nobody gave is unsigned intent wearing a signature.

So an agent-authored record is a **draft**, and a draft has no signature — not a blank one the model
may fill, but none: `check` refuses a draft that arrives carrying one. The signature is stamped by
`sign` from an authenticated identity, never from text. That is invariant 7 made structural rather
than procedural: the agent cannot approve its own work because there is nowhere in a draft for an
approval to be written.

State is a projection over the chain — proposed, signed, rejected — so it survives a restart and
cannot disagree with the record of what happened. Pure stdlib, pure over its inputs.
"""
import copy

from .ir import IRValidationError, record_key, validate_record

PROPOSED = "IR_PROPOSED"
SIGNED = "IR_SIGNED"
REJECTED = "IR_PROPOSAL_REJECTED"

#: Used only to run the rest of `validate_record` over a draft. Never stored and never shown as if it
#: were a name.
_PLACEHOLDER = "<awaiting signature>"

#: Fields of `source` that are a person's act. A draft carries neither.
SIGNATURE_FIELDS = ("signed_by", "date")


class ProposalError(Exception): ...


def check(raw: dict) -> list[str]:
    """Everything wrong with a draft, all at once. Empty means it could be signed as it stands."""
    if not isinstance(raw, dict):
        return [f"A record is an object, not a {type(raw).__name__}."]
    source = raw.get("source") or {}
    problems = []
    given = [f for f in SIGNATURE_FIELDS if str(source.get(f) or "").strip()]
    if given:
        problems.append(
            f"source.{' and source.'.join(given)} written by the drafter. A signature is a "
            f"person's act and is stamped from an authenticated identity when they sign; a draft "
            f"arrives without one. A model that writes a name here is asserting an approval nobody "
            f"gave.")
    if not str(source.get("workbook") or "").strip():
        problems.append("source.workbook is empty. A draft says where its values came from — the "
                        "document section or decision point — or there is nothing for a signer to "
                        "check it against.")
    try:
        validate_record(for_validation(raw))
    except IRValidationError as ex:
        problems.append(f"IR validation: {ex}")
    return problems


def for_validation(raw: dict) -> dict:
    """The draft with a placeholder signature, so validation can run over everything else.

    For checking only. The result must never be stored or shown: it carries a placeholder where a
    person's name would be, and a caller that kept it would be storing a fake signature."""
    out = copy.deepcopy(raw)
    src = dict(out.get("source") or {})
    for f in SIGNATURE_FIELDS:
        src[f] = src.get(f) or _PLACEHOLDER
    out["source"] = src
    return out


def draft(raw: dict, provenance: list[str]) -> dict:
    """A drafter's record as it is stored: signature fields present and empty, provenance stamped
    by the platform from what the drafter cited rather than from what it typed."""
    out = copy.deepcopy(raw)
    out["source"] = {"workbook": "; ".join(str(p).strip() for p in provenance if str(p).strip()),
                     "signed_by": "", "date": ""}
    return out


def sign(raw: dict, signer: str, on: str) -> dict:
    """The record a person's signature makes loadable. `signer` is an authenticated identity."""
    if not signer.strip() or not on.strip():
        raise ProposalError("A signature needs a person and a date.")
    out = copy.deepcopy(raw)
    src = dict(out.get("source") or {})
    src.update(signed_by=signer, date=on)
    out["source"] = src
    return out


def state(entries: list[dict]) -> list[dict]:
    """Every proposal on the chain, with where it stands. Latest event per record wins, so a
    re-proposal after a rejection is pending again and the rejection stays in the record."""
    latest: dict[str, dict] = {}
    for e in entries:
        action = e.get("action")
        if action == PROPOSED:
            latest[e["task"]] = {"key": e["task"], "record": e.get("record", {}),
                                 "status": "pending", "proposed_by": e.get("actor", ""),
                                 "proposed_on": e.get("ts", ""), "why": e.get("detail", ""),
                                 "resolved_by": "", "resolved_on": "", "reason": ""}
        elif action in (SIGNED, REJECTED) and e["task"] in latest:
            row = latest[e["task"]]
            row.update(status="signed" if action == SIGNED else "rejected",
                       resolved_by=e.get("actor", ""), resolved_on=e.get("ts", ""),
                       reason=e.get("detail", ""))
    return list(latest.values())


def key_of(raw: dict) -> str:
    return record_key(raw)
