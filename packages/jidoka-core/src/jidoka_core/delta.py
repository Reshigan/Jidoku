"""The delta pool: a fixed budget of customisations, debited, and a hard stop when it is empty.

From docs/JIDOKA_PROJECT_TEAM_AND_ALIGNMENT.md §3, step 3 — *"Delta pool debit — consumes one of
the 30 (F1.4); pool empty ⇒ COMMERCIAL DP, not a quiet build."* The economist has priced the pool
in prose since ADR-0020 and there was no pool: a sentence in a run report is not a budget, and a
budget nothing can exhaust is a number in a slide.

What counts as a debit is not a judgement call here, and that is the point of doing this after
ADR-0034: **a customisation is an object with a contract.** Delivered standard configuration
carries none; the objects a programme builds carry one, because they are exactly the objects
somebody has to declare an owner and readers for. So the pool debits on the design, from the same
declaration the contract registry reads, and there is no second list of "things we consider
custom" to keep in step.

The stop is commercial, not technical. An empty pool does not mean the platform cannot build the
thing; it means somebody agreed to thirty and this is the thirty-first, and that is a conversation
with a name on it rather than a build that quietly happens. Hence a COMMERCIAL decision point —
which hard-blocks planning like any other open decision, because invariant 2 does not care where
the question came from.

Pure, stdlib, a projection over the chain and the design.
"""
from .contracts import registry

#: What a programme gets unless it negotiated otherwise. Thirty is the Komatsu number and it is a
#: commercial fact, not a law of nature — which is why it is declared per engagement and this is
#: only the default.
DEFAULT_POOL = 30

#: Where a different size is declared. On the ledger, like the night's cadence, so the pool and
#: what it spent are read off one chain and no second store has to agree with the first.
SIZE_ACTION = "DELTA_POOL"


def size(entries: list[dict]) -> int:
    """How many customisations this engagement bought. The last declaration wins."""
    declared = [e for e in entries if e.get("action") == SIZE_ACTION]
    if not declared:
        return DEFAULT_POOL
    try:
        return max(0, int(declared[-1].get("size", DEFAULT_POOL)))
    except (TypeError, ValueError):
        return DEFAULT_POOL


def spent(records: list) -> list[str]:
    """The customisations this design contains: every object carrying a contract.

    Read off the design rather than counted as they are built, because the commercial question is
    asked when somebody proposes the thirty-first — not after it has been written to a tenant.
    """
    return sorted(registry(records))


def state(records: list, entries: list[dict]) -> dict:
    of = size(entries)
    used = spent(records)
    left = of - len(used)
    return {"of": of, "spent": len(used), "remaining": left, "objects": used,
            "over": max(0, -left),
            "says": (f"{len(used)} of {of} customisations. {left} left."
                     if left > 0 else
                     f"{len(used)} of {of} customisations. The pool is empty — the next one is a "
                     f"commercial conversation, not a build."
                     if left == 0 else
                     f"{len(used)} customisations against a pool of {of}. {-left} over, and "
                     f"somebody agreed to {of}."),
            "method": ("A customisation is an object carrying a cross-module contract (ADR-0034): "
                       "delivered standard configuration has no owner to declare. The pool is "
                       "counted from the design, not from what has been built, because the "
                       "commercial question is asked when somebody proposes the thirty-first — "
                       "not after it has reached a tenant.")}


def question(over: int, of: int) -> str:
    """The decision point's question. Commercial, and addressed to whoever signed the number."""
    return (f"This design contains {over} customisation(s) beyond the {of} this engagement's "
            f"delta pool allows. Extend the pool, drop {over} of them, or take {over} back to the "
            f"delivered standard — JIDOKA will not build past a number somebody agreed to.")
