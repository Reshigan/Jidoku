"""How this platform writes a moment. One definition, because six of them is six chances to drift.

The format was written out at seven call sites — the ledger, the transport tracker, the executor's
arming lapse, the execution router, and two projections that parse `ts` back. That is the failure
mode this codebase keeps finding: a fact stated twice, drifting apart. It is worse than usual here
because a parser reading `ts` with a format the writer no longer uses does not raise. It matches
nothing, and the projection quietly reports that nothing happened.

A leaf: it imports nothing from this package, so the modules that deliberately do not depend on
the ledger — `transport` says so in its own docstring — can still share the one definition.
"""
import time

#: UTC and fixed-width, so string order is time order and a chain can be sorted without parsing.
TS = "%Y-%m-%dT%H:%M:%SZ"


def stamp(epoch: float | None = None) -> str:
    """A moment as this platform writes it. UTC, always: a local time on a chain read in two
    countries is a chain that disagrees with itself about the order of its own entries."""
    return time.strftime(TS, time.gmtime(epoch) if epoch is not None else time.gmtime())
