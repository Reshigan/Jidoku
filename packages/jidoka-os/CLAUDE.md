# CLAUDE.md — jidoka-os
The privilege layer. Read docs/JIDOKA_AGENT_OS.md first.
NEVER: add a capability to MAX_CAPS[Ring.AGENT] or [Ring.SERVICE] that includes APPROVE or RESOLVE_DP (an
import-time assertion guards this); register a syscall without a SYSCALL_TABLE capability; add a path from an
agent to an adapter that bypasses Kernel.dispatch; allow runtime capability acquisition; let restart widen
privilege; make halt clearable by whoever raised it.
Tests here assert what the system CANNOT do. A PR that changes ring ceilings needs an ADR and a failing-test-first.
