"""What the platform can prove, counted from its own chain.

Every other number on this platform is about work: steps planned, records loaded, objects
recovered. This one is about evidence, and it is the number an auditor actually wants — of
everything this engagement says is done, how much can be demonstrated, and how much rests on
somebody's word?

The distinction is not pedantry. A verification that read a live system and found the signed
value is evidence. A person stating they changed a Provisioning switch nobody can read back is a
different kind of thing (ADR-0022): it is evidence about a person. Both are legitimate, both are
on the chain, and a report that added them together would be worth less than one that kept them
apart — because the sum is exactly the number somebody would quote.

So the classification is the product, and the headline is derived from it rather than the other
way round. Every basis below is a ledger action some verification actually wrote; nothing here
infers a state from the absence of one.

Pure over its inputs, stdlib, and a projection: run it twice on the same chain and it says the
same thing, which is what makes it quotable.
"""
from dataclasses import dataclass

from .ir import record_key

#: Ledger actions a verification writes as its verdict on one record. The last one wins: a record
#: unreadable yesterday and attested today is attested.
VERDICTS = ("VERIFIED", "DRIFT_DETECTED", "NOT_APPLIED", "AWAITING_A_PERSON",
            "UNCONFIRMABLE", "ATTESTED")

#: verdict -> what that record's claim to being done rests on.
BASIS = {
    "VERIFIED": "checked",            # the platform read the live system and it matched
    "DRIFT_DETECTED": "disagrees",    # read, and the system says something else
    "ATTESTED": "attested",           # a named person's word; no read path exists
    "UNCONFIRMABLE": "unevidenced",   # no read path and nobody has attested
    "AWAITING_A_PERSON": "outstanding",  # handed over, not done yet — no claim of completion
    "NOT_APPLIED": "unbuilt",         # nothing has been written — no claim of completion
}
UNEXAMINED = "unexamined"             # no verification has ever reached it

#: The bases that assert a record is done. The other three assert the opposite, or nothing.
CLAIMED = ("checked", "disagrees", "attested", "unevidenced")

FORMULA = ("proven = checked / (checked + disagrees + attested + unevidenced). The denominator is "
           "every record something claims is done; the numerator is the subset this platform read "
           "back from the live system itself.")

NOT_COUNTED = ("records nobody has built yet",
               "records handed to a person and still outstanding",
               "records no verification has ever looked at")


@dataclass(frozen=True)
class Assurance:
    records: int
    basis: dict             # basis -> [record key]
    claimed: int
    proven: int
    fraction: float | None  # None when nothing is claimed — never 0.0, which reads as a failure

    def as_dict(self) -> dict:
        return {"records": self.records,
                "basis": {b: list(k) for b, k in sorted(self.basis.items())},
                "counts": {b: len(k) for b, k in sorted(self.basis.items())},
                "claimed": self.claimed, "proven": self.proven, "fraction": self.fraction,
                "formula": FORMULA, "not_counted": list(NOT_COUNTED)}


def verdicts(ledger_entries) -> dict:
    """The latest verdict per record, by ledger action. Later entries supersede earlier ones."""
    out = {}
    for entry in ledger_entries:
        if entry.get("action") in VERDICTS:
            out[entry.get("task")] = entry.get("action")
    return out


def assure(records, ledger_entries) -> Assurance:
    """Classify every signed record by what its claim to being done rests on.

    A record with no verdict is `unexamined` rather than assumed anything: the absence of a check
    is a finding in its own right, and folding it into "not built" would invent a fact about a
    live system nobody has looked at.
    """
    last = verdicts(ledger_entries)
    basis: dict[str, list[str]] = {}
    for record in records:
        key = record_key(record)
        where = BASIS.get(last.get(key), UNEXAMINED)
        basis.setdefault(where, []).append(key)

    claimed = sum(len(basis.get(b, ())) for b in CLAIMED)
    proven = len(basis.get("checked", ()))
    return Assurance(records=sum(len(v) for v in basis.values()), basis=basis, claimed=claimed,
                     proven=proven, fraction=(proven / claimed) if claimed else None)
