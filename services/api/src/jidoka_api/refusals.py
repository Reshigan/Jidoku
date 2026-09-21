"""Every refusal this platform makes, on the chain that records everything else it does.

The gates were the product and they left no trace. A plan blocked on an open statutory decision,
an approval refused because the reviewer was the builder, a live write refused because nothing was
armed — each one returned a 403 or a 409, the operator read it, and it was gone. So the one
question a customer eventually asks about a governance platform had no answer in it: *are these
gates right, or are they friction?*

A refusal is a governance event. It is the platform declining to act, which is the thing it is
bought to do, and it belongs on the ledger beside the work it declined. Recorded here rather than
in each router because a gate that only sometimes records itself is worse than one that never
does — the gaps would read as gates that never fired.

What it records is the route and the status, never the body: a request body can carry a credential
and a refusal is not a reason to persist one. The detail is the platform's own refusal words, which
are already quoted to the operator verbatim.
"""
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

#: The ledger action. A refusal is not a failure — the platform working is exactly what a refusal
#: looks like — so it is its own word rather than an error.
REFUSED = "REFUSED"

#: The same person, past the same gate, later. Written once per clearing and never otherwise: a
#: success that was never refused is ordinary work and already on the chain under its own name.
#: Without this, a refusal record could say how often gates fired and nothing about whether they
#: held — and "how often we said no" on its own is a vanity number.
CLEARED = "CLEARED"

#: Statuses that mean *the platform declined*, as opposed to the client asking for something that
#: does not exist. 401 is absent on purpose: an unauthenticated call is not a gate firing, it is a
#: request that never reached one, and counting them would bury the refusals that mean something.
GATES = {403: "forbidden", 409: "blocked", 422: "refused as invalid"}

#: How much of the platform's own words to keep. Enough to know which gate spoke; a refusal that
#: needs a paragraph to identify is one nobody will read in a list either.
DETAIL_LIMIT = 300


def gate_of(request: Request) -> str:
    """A stable name for the gate that fired: the method and the route template, never the URL.

    The template, so every engagement's refusals of the same gate count as the same gate; without
    it each id would be its own row and a pattern across a portfolio would be invisible.
    """
    route = request.scope.get("route")
    path = getattr(route, "path", None) or request.url.path
    return f"{request.method} {path}"


def engagement_of(request: Request):
    """The engagement whose chain this belongs on, or None. A refusal on a path with no engagement
    — an unknown id, a malformed body before routing — has no chain to go on and is dropped rather
    than pooled somewhere it would be miscounted."""
    eid = request.path_params.get("eid")
    if not eid:
        return None
    from .state import STORE
    try:
        return STORE.get(eid)
    except Exception:                        # noqa: BLE001 — an unknown engagement has no ledger
        return None


def outstanding(entries: list[dict], gate: str, actor: str) -> bool:
    """Has this person been refused at this gate and not got past it since?

    A full pass over the chain, like assurance and the controls do. The chain is the only place
    that knows, and a cached answer that a restart got wrong would understate how often gates hold
    — which is the direction that flatters the platform.
    """
    refused = False
    for entry in entries:
        if entry.get("task") != gate or entry.get("actor") != actor:
            continue
        if entry.get("action") == REFUSED:
            refused = True
        elif entry.get("action") == CLEARED:
            refused = False
    return refused


async def clear(request: Request, status: int) -> None:
    """Record that a gate which had refused this person has now let them through.

    Only for the mutating methods: a GET succeeding after a 403 on the same route means the person
    was given read access, which is an access change and not a gate being cleared.
    """
    if status >= 400 or request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return
    try:
        e = engagement_of(request)
        actor = getattr(getattr(request, "state", None), "subject", "") or "unknown"
        gate = gate_of(request)
        if e is not None and outstanding(e.ledger.entries, gate, actor):
            e.ledger.append(gate, CLEARED, actor,
                            "got past a gate that had refused them here")
    except Exception:                        # noqa: BLE001 — never turn a success into a failure
        pass


async def record(request: Request, exc: HTTPException) -> JSONResponse:
    """Ledger the refusal, then answer exactly as FastAPI would have.

    Recording must never change the answer. A ledger that is down is a reason to lose the record
    of a refusal, never a reason to turn a 403 into a 500 — the operator's refusal message is the
    thing they actually need, and it is the one part of this that cannot fail.
    """
    if exc.status_code in GATES:
        try:
            e = engagement_of(request)
            if e is not None:
                detail = str(exc.detail)[:DETAIL_LIMIT]
                actor = getattr(getattr(request, "state", None), "subject", "") or "unknown"
                e.ledger.append(gate_of(request), REFUSED, actor, detail,
                                status=exc.status_code, gate=GATES[exc.status_code])
        except Exception:                    # noqa: BLE001 — see the docstring
            pass
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                        headers=getattr(exc, "headers", None))
