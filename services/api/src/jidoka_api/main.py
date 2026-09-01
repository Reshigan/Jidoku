from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (auth_router, decisions, engagements, execution, ir, ledger, memory,
                      plans, registry, schema_router)

app = FastAPI(title="goNXT JIDOKA API", version="0.1.0",
              description="SAP automated configuration platform — signed intent in, verified config out.")

# The console is served from a separate origin in development; production fronts both from one host.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

for r in (auth_router, engagements, ir, plans, ledger, decisions, registry, schema_router,
          execution, memory):
    app.include_router(r.router)


@app.get("/health")
def health():
    return {"status": "ok", "invariants": "enforced-in-core"}
