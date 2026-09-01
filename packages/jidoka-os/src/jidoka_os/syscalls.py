"""The syscall boundary: the ONLY way a process touches the world.

Every call is checked in this order — halt state, capability, budget, handler, ledger.
There is no path from an agent to an adapter that bypasses this function. That is the whole design:
the agent's reasoning can be wrong, jailbroken, or adversarial and the reachable action set does not widen."""
from .capabilities import Cap, CapabilityError
from .process import Process, State, BudgetExceeded

class HaltedError(Exception): ...
class SyscallError(Exception): ...

# syscall -> required capability. Adding a syscall REQUIRES choosing its capability (no default).
SYSCALL_TABLE = {
    "sys_extract":        Cap.READ_SYSTEM,
    "sys_plan":           Cap.PLAN,
    "sys_emit_artefact":  Cap.EMIT,
    "sys_write_tier_a":   Cap.WRITE_TARGET,
    "sys_ledger_append":  Cap.LEDGER_WRITE,
    "sys_ledger_approve": Cap.APPROVE,      # unreachable from ring 2+ by construction
    "sys_raise_dp":       Cap.RAISE_DP,
    "sys_resolve_dp":     Cap.RESOLVE_DP,   # human authority
    "sys_halt":           Cap.HALT,
    "sys_spawn":          Cap.SPAWN,
}

class Kernel:
    """Ring 0. Holds the halt flag, the registry, the ledger, and the handler table."""
    def __init__(self, ledger, registry, supervisor):
        self.ledger, self.registry, self.supervisor = ledger, registry, supervisor
        self.halted = False
        self.halt_reason = ""
        self.handlers = {}

    def register(self, name: str, fn):
        if name not in SYSCALL_TABLE:
            raise SyscallError(f"{name} has no capability assignment — add it to SYSCALL_TABLE first.")
        self.handlers[name] = fn

    def halt(self, reason: str, by: str):
        """The andon cord. Any process, any human, any ring. Requires a reason."""
        if not reason.strip():
            raise SyscallError("A halt requires a reason — an unexplained stop teaches nobody anything.")
        self.halted, self.halt_reason = True, reason
        self.ledger.append("kernel", "LINE_HALTED", by, reason)

    def resume(self, by: str, reviewer: str):
        if reviewer == by:
            raise SyscallError("The person who halted the line cannot be the one who clears it.")
        self.halted, self.halt_reason = False, ""
        self.ledger.append("kernel", "LINE_RESUMED", reviewer, f"cleared halt raised by {by}")

    def dispatch(self, proc: Process, call: str, tokens: int = 0, **kwargs):
        if call not in SYSCALL_TABLE:
            raise SyscallError(f"Unknown syscall {call!r}.")
        if proc.state in (State.KILLED, State.TERMINATED):
            raise SyscallError(f"pid {proc.pid} is {proc.state}.")
        # 1. halt beats everything except halting and reading
        if self.halted and call not in ("sys_halt", "sys_extract"):
            raise HaltedError(f"Line halted: {self.halt_reason}. {call} refused.")
        # 2. capability
        required = SYSCALL_TABLE[call]
        if not proc.capabilities.has(required):
            self.ledger.append(f"proc:{proc.pid}", "SYSCALL_DENIED", proc.manifest.name,
                               f"{call} requires {required}")
            raise CapabilityError(
                f"{proc.manifest.name} (ring {proc.capabilities.ring.name}) may not call {call}: "
                f"requires capability '{required}'.")
        # 3. write guard — the registry decides, not the agent
        if call == "sys_write_tier_a":
            self.registry.assert_writable(kwargs.get("system_id", ""))
        # 4. budget
        proc.charge(tokens=tokens)
        # 5. handler
        handler = self.handlers.get(call)
        if handler is None:
            raise SyscallError(f"{call} is not implemented in this kernel build.")
        result = handler(proc=proc, **kwargs)
        # 6. every syscall is evidence
        self.ledger.append(f"proc:{proc.pid}", f"SYSCALL:{call}", proc.manifest.name,
                           kwargs.get("detail", ""))
        return result
