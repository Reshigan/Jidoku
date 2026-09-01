"""Engagement sessions: one OS process and one project memory per engagement, concurrently.

This is the seam that was missing. consultant.run() drove a tool loop with no memory and no
supervision; jidoka-os had processes nobody spawned; jidoka-knowledge has memory nobody reads.
A session binds the three: the agent runs as a supervised process, under a budget, with the
engagement's beliefs in front of it, and what it learns is written back as grounded claims.

Isolation is structural (ADR-0010): a Session holds exactly one ProjectStore, bound to one
engagement_id, and there is no path from one session to another's memory.
"""
import threading

from jidoka_core.ledger import Ledger
from jidoka_knowledge import (Claim, ProjectStore, SystemStore, evidence_hash, sweep,
                              STALE, TRUSTED, UNVERIFIED)
from jidoka_os.economy import architect
from jidoka_os.process import Supervisor, BudgetExceeded

from . import consultant
from .client import JidokaClient

# System memory is process-wide: what JIDOKA knows about SAP, not about any client. Sessions read
# it; only the scrubber gate writes it.
SYSTEM_MEMORY = SystemStore()


def _memory_brief(store: ProjectStore, limit: int = 40) -> str:
    """Render current beliefs for the prompt, badges included.

    Stale claims are shown, not hidden — the agent must know what is uncertain. Suppressing them
    would silently convert uncertainty into absence, which is the failure ADR-0010 exists to stop.
    """
    lines = []
    for c in SYSTEM_MEMORY.current()[:limit]:
        lines.append(f"- [SAP knowledge] {c.text}")
    for c in store.current()[:limit]:
        badge = {TRUSTED: "verified", STALE: "STALE — re-verify before relying on this",
                 UNVERIFIED: "unverified"}[c.status]
        lines.append(f"- [{c.subject}] {c.text} ({badge}; source {c.source_ref})")
    if not lines:
        return "No established beliefs for this engagement yet."
    return "\n".join(lines)


MEMORY_RULES = """
Memory rules: beliefs marked STALE or unverified may not be presented as fact — re-verify them
against the source or say plainly that they are unconfirmed. Never state a client value that is
not in a signed source or an established belief; raise a Decision Point instead."""


class Session:
    """One engagement's agent. Holds its own process, budget, memory and lock.

    The lock serialises turns within an engagement — two concurrent asks against the same
    engagement would interleave tool calls against one plan. Different engagements hold
    different locks and run in parallel, which is the point.
    """

    def __init__(self, engagement_id: str, client: JidokaClient, ledger: Ledger | None = None,
                 supervisor: Supervisor | None = None) -> None:
        self.engagement_id = engagement_id
        self.client = client
        self.ledger = ledger or Ledger()
        self.supervisor = supervisor or Supervisor(self.ledger)
        self.memory = ProjectStore(engagement_id, ledger=self.ledger)
        # architect(): builder capabilities only. APPROVE is absent from Ring.AGENT by assertion,
        # so the role invariant is enforced by the ring, not by the tool list alone.
        self.process = self.supervisor.spawn(architect(), by=f"session:{engagement_id}")
        self._lock = threading.Lock()

    def ask(self, prompt: str, ask_fn=consultant.ask, max_iterations: int | None = None) -> list[dict]:
        """Run one governed turn: memory in, transcript out, budget charged."""
        with self._lock:
            system = (f"{consultant.system_prompt()}\n\n"
                      f"Established beliefs for engagement {self.engagement_id}:\n"
                      f"{_memory_brief(self.memory)}\n{MEMORY_RULES}")

            def ask_with_memory(messages, _system=None):
                return ask_fn(messages, system)

            try:
                transcript = consultant.run(
                    prompt, self.client, ask_fn=ask_with_memory,
                    max_iterations=max_iterations or consultant.MAX_ITERATIONS)
            except BudgetExceeded:
                # The process is already KILLED by charge(); surface it rather than retrying,
                # since a retry under the same budget is just a slower failure.
                raise
            # One syscall's worth of accounting per turn; tokens charged from usage when present.
            self.process.charge(tokens=_tokens(transcript), syscalls=1)
            return transcript

    def remember(self, subject: str, text: str, source_ref: str, evidence, actor: str) -> Claim:
        """Form a grounded belief. Ungrounded text is refused by Claim itself."""
        return self.memory.add(
            Claim(subject, text, source_ref, evidence_hash(evidence), actor))

    def refresh(self, evidence_for) -> dict:
        """Deterministic staleness sweep. No model call, so it is safe to run on every read."""
        return sweep(self.memory, evidence_for)


def _tokens(transcript: list[dict]) -> int:
    """Best-effort token accounting; absent usage charges nothing rather than guessing."""
    return sum(m.get("usage", {}).get("output_tokens", 0)
               for m in transcript if isinstance(m, dict))


class SessionRegistry:
    """Concurrent engagements. One session each, created on demand, never shared.

    ponytail: process-local dict + lock. Multi-worker deployments need the stores backed by the
    per-tenant D1, which is the deployment spec's boundary anyway — swap ProjectStore's backing,
    not this class.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def get(self, engagement_id: str, client_factory) -> Session:
        with self._lock:
            if engagement_id not in self._sessions:
                self._sessions[engagement_id] = Session(engagement_id, client_factory(engagement_id))
            return self._sessions[engagement_id]

    def active(self) -> list[str]:
        return sorted(self._sessions)
