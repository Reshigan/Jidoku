"""Engagement lifecycle states (E2). The phase is earned, not asserted: transitions are ledgered and
only legal along the declared graph. Skipping a phase is refused, not warned about."""
from __future__ import annotations

PHASES = ("DISCOVER", "SCOPE", "BUILD", "CUTOVER", "HYPERCARE")

# Forward-only. There is no path back into BUILD from CUTOVER by transition: a regression is a new
# engagement phase decision made by humans, recorded as such, not a quiet rewind.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "DISCOVER": ("SCOPE",),
    "SCOPE": ("BUILD",),
    "BUILD": ("CUTOVER",),
    "CUTOVER": ("HYPERCARE",),
    "HYPERCARE": (),
}


class LifecycleError(Exception): ...


def can_transition(frm: str, to: str) -> bool:
    if frm not in TRANSITIONS:
        raise LifecycleError(f"Unknown phase {frm!r}")
    return to in TRANSITIONS[frm]


def assert_transition(frm: str, to: str) -> None:
    if to not in PHASES:
        raise LifecycleError(f"Unknown phase {to!r} — phases are {list(PHASES)}.")
    if not can_transition(frm, to):
        allowed = TRANSITIONS[frm]
        nxt = f"next is {allowed[0]}" if allowed else "this is the final phase"
        raise LifecycleError(f"{frm} does not advance to {to} — {nxt}.")
