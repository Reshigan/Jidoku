"""Number ranges: external codes as governed allocations, not naming conventions.

On a real SAP programme the number range concept (SNRO, externalCode conventions, wage type
series) is where two consultants silently collide: both pick the next "obvious" code and the
clash surfaces in integration testing. Here a range is registered once, every allocation is
appended to the ledger, and a collision is refused at allocation time — the earliest moment it
can be seen. Codes are never released for reuse: a code that once named an object keeps naming
it in every document, ledger entry and downstream system that ever saw it.
"""
import re
from dataclasses import dataclass, field


class NumberingError(Exception):
    """A refusal — a collision, an exhausted range, a code outside every registered range."""


@dataclass
class NumberRange:
    range_id: str
    object_type: str          # the IR object this range governs, e.g. "TimeType"
    prefix: str               # e.g. "TT_ZA_"
    start: int
    end: int                  # inclusive
    width: int = 4            # zero-padding of the numeric part

    def __post_init__(self):
        if self.start < 0 or self.end < self.start:
            raise NumberingError(f"{self.range_id}: empty range [{self.start}, {self.end}].")

    def format(self, n: int) -> str:
        return f"{self.prefix}{n:0{self.width}d}"

    def parse(self, code: str) -> int | None:
        """The number this code occupies in this range, or None if the code is not from it."""
        m = re.fullmatch(re.escape(self.prefix) + r"(\d+)", code)
        if not m:
            return None
        n = int(m.group(1))
        return n if self.start <= n <= self.end else None


class NumberRanges:
    """Per-engagement range registry. Every mutation lands on the engagement's ledger."""

    def __init__(self, ledger):
        self.ledger = ledger
        self._ranges: dict[str, NumberRange] = {}
        self._allocated: dict[str, str] = {}   # code -> allocated_by

    def register(self, rng: NumberRange, actor: str) -> NumberRange:
        if rng.range_id in self._ranges:
            raise NumberingError(f"{rng.range_id}: already registered.")
        for other in self._ranges.values():
            if (other.object_type == rng.object_type and other.prefix == rng.prefix
                    and other.start <= rng.end and rng.start <= other.end):
                raise NumberingError(
                    f"{rng.range_id} overlaps {other.range_id} on {rng.object_type} "
                    f"({rng.prefix}{rng.start}..{rng.end} vs {other.start}..{other.end}) — "
                    f"two ranges handing out the same codes is the collision this exists to prevent.")
        self._ranges[rng.range_id] = rng
        # The range's full shape rides in the entry so a cold process can rebuild the registry
        # from the ledger alone — the ledger is already the durable record of every allocation.
        self.ledger.append(rng.range_id, "RANGE_REGISTERED", actor,
                           f"{rng.object_type}: {rng.format(rng.start)}..{rng.format(rng.end)}",
                           range=vars(rng))
        return rng

    def rehydrate(self) -> None:
        """Rebuild ranges and allocations from the ledger this instance was handed.

        Replays, never re-appends: appending during rehydration would duplicate the chain.
        """
        for e in getattr(self.ledger, "entries", []):
            if e.get("action") == "RANGE_REGISTERED" and e.get("range"):
                r = NumberRange(**e["range"])
                self._ranges[r.range_id] = r
            elif e.get("action") == "CODE_ALLOCATED":
                self._allocated[e["task"]] = e.get("actor", "?")

    def _ranges_for(self, object_type: str) -> list[NumberRange]:
        return [r for r in self._ranges.values() if r.object_type == object_type]

    def allocate(self, object_type: str, actor: str, code: str | None = None) -> str:
        """Next free code from the object's range, or a requested code if it is free and inside one.

        Requested codes exist because workbooks arrive with codes already chosen; the gate is
        that the choice must land inside a governed range and on an unclaimed number.
        """
        ranges = self._ranges_for(object_type)
        if not ranges:
            raise NumberingError(f"No number range is registered for {object_type} — register one "
                                 f"before allocating.")
        if code is not None:
            if code in self._allocated:
                raise NumberingError(f"{code}: already allocated by {self._allocated[code]}.")
            if not any(r.parse(code) is not None for r in ranges):
                raise NumberingError(f"{code}: outside every registered {object_type} range.")
            self._allocated[code] = actor
            self.ledger.append(code, "CODE_ALLOCATED", actor, f"{object_type}: requested code",
                               object_type=object_type)
            return code
        for r in sorted(ranges, key=lambda x: x.range_id):
            for n in range(r.start, r.end + 1):
                candidate = r.format(n)
                if candidate not in self._allocated:
                    self._allocated[candidate] = actor
                    self.ledger.append(candidate, "CODE_ALLOCATED", actor,
                                       f"{object_type}: next free in {r.range_id}",
                                       object_type=object_type)
                    return candidate
        raise NumberingError(f"Every registered {object_type} range is exhausted.")

    def validate(self, object_type: str, code: str | None) -> str | None:
        """None if acceptable; otherwise the reason it is not.

        An object type with no registered range is unconstrained — ranges opt an object type in,
        so engagements that never touch numbering lose nothing.
        """
        ranges = self._ranges_for(object_type)
        if not ranges or code is None:
            return None
        if any(r.parse(code) is not None for r in ranges):
            return None
        governed = ", ".join(f"{r.format(r.start)}..{r.format(r.end)}" for r in
                             sorted(ranges, key=lambda x: x.range_id))
        return (f"{code}: outside every registered {object_type} range ({governed}). "
                f"Allocate from the range, or register a range that covers this code.")

    def snapshot(self) -> dict:
        return {"ranges": [{**vars(r), "next_free": self._next_free(r)} for r in
                           sorted(self._ranges.values(), key=lambda x: x.range_id)],
                "allocated": dict(sorted(self._allocated.items()))}

    def _next_free(self, r: NumberRange) -> str | None:
        for n in range(r.start, r.end + 1):
            if r.format(n) not in self._allocated:
                return r.format(n)
        return None
