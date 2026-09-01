"""Typed Decision Point engine. STATUTORY and ONE_WAY are hard gates by construction."""
from dataclasses import dataclass, field

DP_TYPES = ("DESIGN", "STATUTORY", "ONE_WAY", "SEQUENCE", "COMMERCIAL")

class DecisionError(Exception): ...

@dataclass
class DecisionPoint:
    dp_id: str
    dp_type: str
    question: str
    owner: str
    options: list = field(default_factory=list)
    resolution: dict | None = None

class DecisionEngine:
    def __init__(self, ledger):
        self.ledger = ledger
        self.dps: dict[str, DecisionPoint] = {}

    def raise_dp(self, dp: DecisionPoint) -> DecisionPoint:
        if dp.dp_type not in DP_TYPES:
            raise DecisionError(f"Unknown DP type {dp.dp_type}")
        self.dps[dp.dp_id] = dp
        self.ledger.append(dp.dp_id, "DP_RAISED", "jidoka", f"{dp.dp_type}: {dp.question} -> {dp.owner}")
        return dp

    def resolve(self, dp_id: str, decided_by: str, value, evidence_ref: str,
                second_approver: str | None = None):
        dp = self.dps[dp_id]
        if dp.dp_type == "STATUTORY" and not evidence_ref:
            raise DecisionError(f"{dp_id}: STATUTORY DP requires a signed client evidence reference.")
        if dp.dp_type == "ONE_WAY":
            if not second_approver or second_approver == decided_by:
                raise DecisionError(f"{dp_id}: ONE_WAY DP requires two distinct named approvers.")
        dp.resolution = {"by": decided_by, "value": value, "evidence": evidence_ref,
                         "second_approver": second_approver}
        self.ledger.append(dp_id, "DP_RESOLVED", decided_by,
                           f"value={value!r} evidence={evidence_ref}", second_approver=second_approver or "")
        return dp
