"""Drift: the live system disagreeing with signed intent.

Every configuration platform reports drift. JIDOKA treats it as something stronger: an open
question with a named owner. When a verification run finds a live value that signed intent does
not explain, the platform does not re-apply the intent (that overwrites a change nobody has
understood yet) and does not adopt the observed value (that launders an unsigned change into the
record). It appends the finding to the ledger and raises a decision point that blocks planning
until a human chooses — reassert the signed intent, or sign new intent that says the observed
state is now the design. Drift is a decision, not a report (ADR-0013).
"""
from dataclasses import dataclass, field

from .decisions import DecisionPoint


#: A record that signed intent describes and nobody has built yet. Not drift: nothing changed
#: under anyone, because nothing was ever there. It is a status, and the plan is what closes it.
NOT_APPLIED = "NOT_APPLIED"


@dataclass
class DriftFinding:
    """One record whose live state does not match its signed intent."""
    key: str
    status: str                       # DRIFT | MISSING | NOT_APPLIED
    system: str
    fields: dict = field(default_factory=dict)   # field -> {"intent": ..., "live": ...}
    dp_id: str | None = None          # the decision point now blocking this record


def dp_id_for(key: str) -> str:
    return f"DP-DRIFT-{key}"


class DriftWatch:
    """Turns adapter verification verdicts into ledger entries and blocking decisions.

    Pure over its inputs: the caller reads the live system (through a bound connector) and hands
    each record's verdict in. The watch owns only the governance consequence, so no client can
    reach the live system and skip it.
    """

    def __init__(self, ledger, decisions):
        self.ledger = ledger
        self.decisions = decisions

    def observe(self, record, verification: dict, actor: str,
                applied: bool = True) -> DriftFinding | None:
        """One record, one verdict. Returns the finding, or None when live state matches.

        `applied` says whether this platform has ever written the record — an EXECUTED entry on
        its chain. It matters for exactly one case, and getting that case wrong makes the Verify
        button unusable: a record that signed intent describes and nobody has built yet is absent
        from the live system for the most ordinary reason there is. Calling that drift raises a
        decision whose two answers — reassert the intent, or adopt the observed state — are both
        wrong, and blocks planning on a question whose real answer is "build it". So absence
        before a build is NOT_APPLIED, and it raises nothing.

        Absence *after* a build is drift and always was: we put it there and it is gone. And a
        record that is present but disagrees is drift whether or not we wrote it — in fact a
        record we never wrote that exists anyway is the most interesting finding on the page,
        because somebody configured it outside this platform.
        """
        status = verification.get("status")
        key = record.key
        dp_id = dp_id_for(key)
        open_dp = dp_id in self.decisions.dps and self.decisions.dps[dp_id].resolution is None

        if status == "MATCH":
            if open_dp:
                # The live system matches again — but something changed it twice without a signed
                # record, and the second change is as unexplained as the first. The owner still
                # answers; a self-healing anomaly is an anomaly with better timing.
                self.ledger.append(key, "VERIFIED", actor,
                                   f"live state matches signed intent; {dp_id} remains open — "
                                   f"the drift that was observed is still unexplained")
            else:
                self.ledger.append(key, "VERIFIED", actor, "live state matches signed intent")
            return None

        fields = verification.get("drift", {}) or {}
        if status == "MISSING" and not applied:
            self.ledger.append(key, "NOT_APPLIED", actor,
                               f"absent from {record.system_binding}; this platform has never "
                               f"written it, so there is nothing to explain — it is unbuilt work",
                               status=NOT_APPLIED, system=record.system_binding)
            return DriftFinding(key=key, status=NOT_APPLIED, system=record.system_binding,
                                fields={}, dp_id=None)
        if status == "MISSING":
            detail = (f"record absent from live system {record.system_binding} — signed intent "
                      f"says it exists")
        else:
            named = ", ".join(sorted(fields)) or "unknown fields"
            detail = f"live values differ from signed intent on: {named}"
        self.ledger.append(key, "DRIFT_DETECTED", actor, detail,
                           status=status, fields=fields, system=record.system_binding)

        if not open_dp:
            owner = (record.source or {}).get("signed_by") or "engagement lead"
            self.decisions.raise_dp(DecisionPoint(
                dp_id=dp_id, dp_type="DESIGN",
                question=(f"{key}: {detail}. Reassert the signed intent (re-apply), or adopt the "
                          f"observed state (requires a new signed IR record)?"),
                owner=owner,
                options=["reassert signed intent — re-apply the IR record",
                         "adopt observed state — sign a new IR record that says so"]))
        return DriftFinding(key=key, status=status, system=record.system_binding,
                            fields=fields, dp_id=dp_id)
