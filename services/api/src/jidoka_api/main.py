from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from . import refusals

from .routers import (accountability, auth_router, controls, decisions, documents, engagements,
                      execution, insight, ir, ledger, memory, nightshift, numbering, people,
                      plans, portfolio, registry, run, schema_router, twin, verification)
from .state import STORE

app = FastAPI(title="goNXT JIDOKA API", version="0.1.0",
              description="SAP automated configuration platform — signed intent in, verified config out.")

# The console is served from a separate origin in development; production fronts both from one host.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# A refusal is the platform working, and it belongs on the chain beside the work it declined.
# Registered once, centrally: a gate that only sometimes records itself would read as a gate that
# never fired (ADR-0031).
app.add_exception_handler(HTTPException, refusals.record)

for r in (auth_router, engagements, ir, plans, ledger, decisions, documents, registry, schema_router,
          execution, memory, numbering, verification, insight, run, controls, twin,
          nightshift, people, accountability, portfolio):
    app.include_router(r.router)


@app.middleware("http")
async def note_when_a_gate_is_cleared(request, call_next):
    """A refusal on the chain says a gate fired; this says whether it held (ADR-0031).

    Recorded at the same seam as the refusal, so the two cannot disagree about what a gate is —
    and only when there is an outstanding refusal to clear, which is what keeps a record of every
    gate from becoming a record of every request.
    """
    response = await call_next(request)
    await refusals.clear(request, response.status_code)
    return response


@app.get("/health")
def health(response: Response):
    """Liveness and readiness in one endpoint, because a host that gates rollout on a probe that
    only proves uvicorn started will happily promote a kernel with no store behind it.

    The store is what makes the ledger durable. A kernel that answers 200 while unable to read its
    own engagements is worse than one that is plainly down: the console renders, the operator
    trusts it, and the first append is lost. So the check is a real read against the repository.
    """
    checks = {}
    try:
        STORE.list()
        checks["store"] = "ok"
    except Exception as ex:                  # noqa: BLE001 — any store failure means not ready
        # The class, never the message: a DSN in an exception string is a leaked credential.
        checks["store"] = f"unavailable ({type(ex).__name__})"

    ready = all(v == "ok" for v in checks.values())
    if not ready:
        response.status_code = 503
    return {"status": "ok" if ready else "degraded", "checks": checks,
            "invariants": "enforced-in-core"}
