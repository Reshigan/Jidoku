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


@dataclass
class DriftFinding:
    """One record whose live state does not match its signed intent."""
    key: str
    status: str                       # DRIFT | MISSING
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

    def observe(self, record, verification: dict, actor: str) -> DriftFinding | None:
        """One record, one verdict. Returns the finding, or None when live state matches."""
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
