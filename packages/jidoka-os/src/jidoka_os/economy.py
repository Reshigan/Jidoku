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

# --- module agents: one process per module, derived from the design ----------------------------
# "Every module agent, every human, every document reads the same graph. There is no EC version of
# the design to diverge from the Time Off version" (docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT §4.1).
# So the set of module agents is not a constant here: it is whichever modules the signed intent
# declares as contract owners. A hardcoded list would be a second statement of the design, and the
# day a programme added a module it would be the stale one.


def module_agent(module: str) -> Manifest:
    """One module's agent. Ring 2, like every other agent: builder at most, approver never.

    Its objective is deliberately narrow and deliberately in tension with its neighbours'. A
    module agent that wanted the whole programme to go well would agree with everybody, and the
    cross-module collisions this exists to surface are exactly the ones both sides are relaxed
    about.
    """
    return Manifest(f"module:{module}", Ring.AGENT,
                    {Cap.READ_SYSTEM, Cap.PLAN, Cap.EMIT, Cap.LEDGER_WRITE, Cap.RAISE_DP, Cap.HALT},
                    objective=f"configure {module} to signed intent, and object to anything that "
                              f"writes or reads across its contract without declaring it")


def pmo() -> Manifest:
    """The schedule, honestly. Ring 3: it reads and it says so, and it writes nothing — a PMO
    agent that could move a date would be a PMO agent whose forecasts always came true."""
    return Manifest("pmo", Ring.UNTRUSTED, {Cap.READ_SYSTEM, Cap.HALT},
                    objective="make the schedule honest: what is actually done, what is waiting "
                              "on a person, and what that means for the date")


def migration() -> Manifest:
    """Data migration: eighteen steps and a reconciliation. Ring 2 and no WRITE_TARGET — loading a
    customer's data is an execution, and it goes through the executor with everything else."""
    return Manifest("migration", Ring.AGENT,
                    {Cap.READ_SYSTEM, Cap.PLAN, Cap.EMIT, Cap.LEDGER_WRITE, Cap.HALT},
                    objective="every record accounted for: loaded, rejected with a reason, or "
                              "deliberately out of scope — never missing")


def integration() -> Manifest:
    """The interfaces between systems. Ring 1, because an interface is plumbing the platform runs
    rather than a position it takes."""
    return Manifest("integration", Ring.SERVICE,
                    {Cap.READ_SYSTEM, Cap.PLAN, Cap.EMIT, Cap.LEDGER_WRITE, Cap.HALT},
                    objective="every mapping traced end to end: no field arrives anywhere by "
                              "accident and none leaves without a destination")


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
