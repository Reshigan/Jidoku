"""A claim is a belief with its receipt attached.

Text is not memory. "The cost centre hierarchy is standard" is unfalsifiable a month later, when
nobody can say what it was read from or whether that thing still says it. A claim carries the
evidence reference it was formed from and the hash of that evidence at formation time, which is
what lets staleness be a comparison rather than a judgement (ADR-0010).
"""
import hashlib, json
from datetime import datetime, timezone


def now() -> str:
    """UTC timestamp with microseconds.

    Whole seconds are too coarse: a correction formed in the same second as the claim it
    supersedes would leave both open at that instant, and as_of() could not order them.
    Timestamps are compared as strings, so the format must sort lexicographically — which is
    exactly what a fixed-width ISO-8601 UTC stamp does.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"

TRUSTED = "TRUSTED"   # evidence re-checked, hash matches
STALE = "STALE"       # evidence moved under it; still held, flagged, not deleted
UNVERIFIED = "UNVERIFIED"  # never re-checked since formation


def evidence_hash(evidence) -> str:
    """Stable hash of whatever the claim was grounded in.

    sort_keys so a dict that round-trips through JSON in a different order is not a false drift;
    default=str so a datetime or Decimal in live SAP state hashes rather than raising.
    """
    return hashlib.sha256(
        json.dumps(evidence, sort_keys=True, default=str).encode()
    ).hexdigest()


class Claim:
    """One belief, grounded. Immutable once formed — correction supersedes, never edits.

    valid_to is None while the claim stands. Superseding closes the interval instead of deleting
    the row, so the store can answer "what did we believe in March" as well as "what now".
    """

    __slots__ = ("id", "subject", "text", "source_ref", "source_hash", "confidence",
                 "status", "valid_from", "valid_to", "supersedes", "actor")

    def __init__(self, subject: str, text: str, source_ref: str, source_hash: str,
                 actor: str, confidence: float = 1.0, supersedes: str | None = None) -> None:
        if not source_ref:
            raise ValueError("a claim without a source is not storable (ADR-0010)")
        self.subject = subject
        self.text = text
        self.source_ref = source_ref
        self.source_hash = source_hash
        self.actor = actor
        self.confidence = confidence
        self.supersedes = supersedes
        self.status = UNVERIFIED
        self.valid_from = now()
        self.valid_to = None
        # Identity derives from content+time so two identical beliefs formed at different moments
        # remain distinguishable in the supersession chain.
        self.id = hashlib.sha256(
            f"{subject}|{text}|{source_ref}|{self.valid_from}".encode()
        ).hexdigest()[:16]

    @property
    def open(self) -> bool:
        return self.valid_to is None

    def close(self, when: str | None = None) -> None:
        self.valid_to = when or now()

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__slots__}

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        c = cls.__new__(cls)
        for k in cls.__slots__:
            setattr(c, k, d.get(k))
        return c

    def __repr__(self) -> str:
        return f"<Claim {self.id} {self.status} {self.subject}: {self.text[:40]!r}>"
