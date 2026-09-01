"""Rings and capabilities. Authority is granted at spawn and cannot be widened at runtime —
a process may drop capabilities but never acquire them (one-way privilege, POSIX-style but stricter)."""
from enum import IntEnum
from dataclasses import dataclass, field

class Ring(IntEnum):
    KERNEL = 0
    SERVICE = 1
    AGENT = 2
    UNTRUSTED = 3

class Cap:
    READ_SYSTEM   = "read_system"     # extract state from a registered system
    PLAN          = "plan"            # build a run plan from IR
    EMIT          = "emit_artefact"   # produce files/instruction sheets (no execution)
    WRITE_TARGET  = "write_target"    # Tier-A writes to a TARGET-role system
    LEDGER_WRITE  = "ledger_write"    # append snapshot/executed evidence
    APPROVE       = "approve"         # NEVER granted to any agent process — see MAX_CAPS
    RAISE_DP      = "raise_dp"        # escalate a decision instead of guessing
    RESOLVE_DP    = "resolve_dp"      # human authority only
    HALT          = "halt"            # the andon cord: universal, held by everyone
    SPAWN         = "spawn"           # create child processes

# The ceiling per ring. Enforced at spawn: a manifest may request less, never more.
MAX_CAPS = {
    Ring.KERNEL:    {Cap.READ_SYSTEM, Cap.PLAN, Cap.EMIT, Cap.WRITE_TARGET, Cap.LEDGER_WRITE,
                     Cap.APPROVE, Cap.RAISE_DP, Cap.RESOLVE_DP, Cap.HALT, Cap.SPAWN},
    Ring.SERVICE:   {Cap.READ_SYSTEM, Cap.PLAN, Cap.EMIT, Cap.WRITE_TARGET, Cap.LEDGER_WRITE,
                     Cap.RAISE_DP, Cap.HALT},
    Ring.AGENT:     {Cap.READ_SYSTEM, Cap.PLAN, Cap.EMIT, Cap.WRITE_TARGET, Cap.LEDGER_WRITE,
                     Cap.RAISE_DP, Cap.HALT, Cap.SPAWN},
    Ring.UNTRUSTED: {Cap.READ_SYSTEM, Cap.HALT},
}
# Structural invariant: approval authority exists in no ring an agent can occupy.
assert Cap.APPROVE not in MAX_CAPS[Ring.AGENT]
assert Cap.APPROVE not in MAX_CAPS[Ring.SERVICE]
assert Cap.RESOLVE_DP not in MAX_CAPS[Ring.AGENT]

class CapabilityError(Exception): ...

@dataclass
class CapabilitySet:
    ring: Ring
    caps: set = field(default_factory=set)

    def __post_init__(self):
        illegal = self.caps - MAX_CAPS[self.ring]
        if illegal:
            raise CapabilityError(
                f"Ring {self.ring.name} may not hold {sorted(illegal)} — "
                f"privilege ceiling is set by the ring, not by the manifest.")

    def has(self, cap: str) -> bool:
        return cap in self.caps

    def drop(self, cap: str) -> "CapabilitySet":
        return CapabilitySet(self.ring, self.caps - {cap})

    def grant(self, cap: str):
        raise CapabilityError("Capabilities cannot be acquired at runtime. Respawn with a new manifest.")
