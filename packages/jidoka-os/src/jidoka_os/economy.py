"""The agent economy (C5): processes with opposed objectives and no shared memory.
Isolation is structural — agents exchange typed messages through the kernel, never a common scratchpad."""
from dataclasses import dataclass, field
from .capabilities import Ring, Cap
from .process import Manifest

def architect() -> Manifest:
    return Manifest("architect", Ring.AGENT,
                    {Cap.READ_SYSTEM, Cap.PLAN, Cap.EMIT, Cap.LEDGER_WRITE, Cap.RAISE_DP, Cap.HALT},
                    objective="maximise fit-to-standard within constraints")

def auditor() -> Manifest:
    return Manifest("auditor", Ring.UNTRUSTED, {Cap.READ_SYSTEM, Cap.HALT},
                    objective="maximise findings: unproven claims, missing evidence, control gaps")

def sentinel() -> Manifest:
    return Manifest("statutory-sentinel", Ring.AGENT,
                    {Cap.READ_SYSTEM, Cap.RAISE_DP, Cap.HALT},
                    objective="detect any value that should be a signed client source")

def operator() -> Manifest:
    return Manifest("operator", Ring.SERVICE,
                    {Cap.READ_SYSTEM, Cap.PLAN, Cap.WRITE_TARGET, Cap.LEDGER_WRITE, Cap.HALT},
                    objective="minimise execution risk: sequencing, rollback viability, cutover feasibility")

def economist() -> Manifest:
    return Manifest("economist", Ring.UNTRUSTED, {Cap.READ_SYSTEM, Cap.HALT},
                    objective="price delta pool, cost of delay, lifetime cost of every custom object")

@dataclass
class Message:
    frm: str; to: str; kind: str; body: dict = field(default_factory=dict)

class MessageBus:
    """No shared memory. Messages are typed, logged, and readable by humans — disagreement is the product."""
    def __init__(self, ledger):
        self.ledger, self.log = ledger, []
    def send(self, msg: Message):
        self.log.append(msg)
        self.ledger.append(f"ipc:{msg.frm}->{msg.to}", "MESSAGE", msg.frm, msg.kind)
    def objections(self) -> list:
        return [m for m in self.log if m.kind == "OBJECTION"]
