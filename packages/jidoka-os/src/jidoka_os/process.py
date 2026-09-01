"""Agent processes: manifest, lifecycle, resource budgets. Tokens are CPU time; exceeding budget
terminates the process rather than degrading silently."""
from dataclasses import dataclass, field
from enum import Enum
import itertools
from .capabilities import CapabilitySet, Ring, MAX_CAPS, CapabilityError

_pid = itertools.count(1)

class State(str, Enum):
    READY = "READY"; RUNNING = "RUNNING"; BLOCKED = "BLOCKED"
    TERMINATED = "TERMINATED"; KILLED = "KILLED"

class BudgetExceeded(Exception): ...

@dataclass
class Manifest:
    name: str
    ring: Ring
    caps: set
    token_budget: int = 100_000
    syscall_budget: int = 500
    objective: str = ""          # agents in the economy hold OPPOSED objectives (C5)
    parent: int | None = None

@dataclass
class Process:
    manifest: Manifest
    pid: int = field(default_factory=lambda: next(_pid))
    state: State = State.READY
    tokens_used: int = 0
    syscalls_made: int = 0
    exit_reason: str = ""
    capabilities: CapabilitySet = None

    def __post_init__(self):
        self.capabilities = CapabilitySet(self.manifest.ring, set(self.manifest.caps))

    def charge(self, tokens: int = 0, syscalls: int = 1):
        self.tokens_used += tokens
        self.syscalls_made += syscalls
        if self.tokens_used > self.manifest.token_budget:
            self.state = State.KILLED
            self.exit_reason = "token budget exceeded"
            raise BudgetExceeded(f"pid {self.pid} ({self.manifest.name}): {self.exit_reason}")
        if self.syscalls_made > self.manifest.syscall_budget:
            self.state = State.KILLED
            self.exit_reason = "syscall budget exceeded"
            raise BudgetExceeded(f"pid {self.pid} ({self.manifest.name}): {self.exit_reason}")

class Supervisor:
    """Spawn/kill/restart with an explicit policy. A killed agent never restarts with wider capabilities."""
    def __init__(self, ledger):
        self.ledger = ledger
        self.table: dict[int, Process] = {}

    def spawn(self, manifest: Manifest, by: str = "kernel") -> Process:
        if manifest.ring == Ring.KERNEL:
            raise CapabilityError("No process may be spawned into ring 0. The kernel is not a process.")
        p = Process(manifest)
        self.table[p.pid] = p
        self.ledger.append(f"proc:{p.pid}", "SPAWNED", by,
                           f"{manifest.name} ring={manifest.ring.name} caps={sorted(manifest.caps)}")
        return p

    def kill(self, pid: int, reason: str, by: str = "kernel"):
        p = self.table[pid]
        p.state = State.KILLED; p.exit_reason = reason
        self.ledger.append(f"proc:{pid}", "KILLED", by, reason)

    def restart(self, pid: int, by: str = "supervisor") -> Process:
        old = self.table[pid]
        m = old.manifest
        # restart is never a privilege escalation opportunity
        safe = Manifest(m.name, m.ring, set(m.caps) & MAX_CAPS[m.ring],
                        m.token_budget, m.syscall_budget, m.objective, m.parent)
        return self.spawn(safe, by)
