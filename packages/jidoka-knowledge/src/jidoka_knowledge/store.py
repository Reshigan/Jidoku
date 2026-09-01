"""Project and system memory. Same interface, different scope — the scope is the security property.

ProjectStore is bound to one engagement_id at construction and has no method that takes another
one. SystemStore holds only what is true of SAP, never of a client. Nothing moves from the first
to the second except through scrubber.promote (ADR-0010).
"""
from .claim import Claim, TRUSTED, STALE, UNVERIFIED


class _Store:
    """Supersession-governed claim set. Never deletes; closes validity intervals."""

    def __init__(self) -> None:
        self._claims: list[Claim] = []

    def add(self, claim: Claim) -> Claim:
        if claim.supersedes:
            prior = self.get(claim.supersedes)
            if prior is None:
                raise KeyError(f"cannot supersede unknown claim {claim.supersedes}")
            prior.close(claim.valid_from)
        self._claims.append(claim)
        return claim

    def get(self, claim_id: str) -> Claim | None:
        return next((c for c in self._claims if c.id == claim_id), None)

    def current(self, subject: str | None = None) -> list[Claim]:
        """Open claims. "Current" is computed from the intervals, never stored as a flag."""
        return [c for c in self._claims
                if c.open and (subject is None or c.subject == subject)]

    def as_of(self, when: str, subject: str | None = None) -> list[Claim]:
        """What was believed at a point in time — the intervals make this free."""
        return [c for c in self._claims
                if c.valid_from <= when and (c.valid_to is None or c.valid_to > when)
                and (subject is None or c.subject == subject)]

    def stale(self) -> list[Claim]:
        return [c for c in self._claims if c.open and c.status == STALE]

    def all(self) -> list[Claim]:
        return list(self._claims)


class ProjectStore(_Store):
    """One engagement's beliefs. Values live here and only here.

    No method accepts an engagement_id: the store *is* the scope. Reading another engagement's
    memory is absent from the API rather than rejected by a check, which is why two projects
    running concurrently cannot cross (ADR-0010).
    """

    def __init__(self, engagement_id: str, ledger=None) -> None:
        super().__init__()
        self.engagement_id = engagement_id
        self._ledger = ledger

    def add(self, claim: Claim) -> Claim:
        claim = super().add(claim)
        # A belief write is a config write: same audit surface, same ledger.
        if self._ledger is not None:
            self._ledger.append(
                task=f"memory:{claim.subject}", action="BELIEF", actor=claim.actor,
                detail=claim.text, claim_id=claim.id, source_ref=claim.source_ref,
                supersedes=claim.supersedes or "",
            )
        return claim


class SystemStore(_Store):
    """Cross-project memory: principles, promoted skills, SAP corpus. Never client values.

    Principles are near-immutable — changing one is itself a decision point, so they are seeded
    at construction and carry no supersession path through ordinary agent action.
    """

    def __init__(self, ledger=None) -> None:
        super().__init__()
        self._ledger = ledger

    def add(self, claim: Claim) -> Claim:
        claim = super().add(claim)
        if self._ledger is not None:
            self._ledger.append(
                task=f"system-memory:{claim.subject}", action="BELIEF", actor=claim.actor,
                detail=claim.text, claim_id=claim.id, source_ref=claim.source_ref,
                supersedes=claim.supersedes or "",
            )
        return claim
