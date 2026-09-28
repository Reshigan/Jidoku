"""The specification, against the configuration.

Every engagement has both and nobody can join them. The requirements are in a Word document, the
configuration is in a system, and the answer to *"which requirements does this actually satisfy?"*
is somebody's memory of a workshop. This router holds the specification a pack was absorbed from
and reports it against signed intent — including, loudly, the requirements it cannot answer for.

Tracing a requirement to an object is a judgement about a client's design, so it takes a person and
it goes on the chain under their name. The platform never infers it: a requirement matched to an
object because a sentence happened to contain its name would report the specification as met.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.requirements import (Control, Requirement, RequirementError, Specification,
                                      account)
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/specification", tags=["specification"])

TRACED = "REQUIREMENT_TRACED"

#: The specification per engagement, and the traceability people have added to it. Declarations,
#: not outcomes: what somebody *did* is on the chain, and the trace is replayed from there.
_SPECS: dict[str, Specification] = {}


class SpecificationIn(BaseModel):
    requirements: list[dict] = []
    controls: list[dict] = []


class Trace(BaseModel):
    objects: list[str]
    why: str = ""


def _spec_or_404(eid: str) -> Specification:
    spec = _SPECS.get(eid)
    if spec is None:
        raise HTTPException(404, "No specification has been absorbed for this engagement. A pack's "
                                 "requirements and control objectives are registered before they "
                                 "can be reported against — an unanswered specification is not the "
                                 "same as one with no requirements in it.")
    return spec


def _traced(entries: list[dict]) -> dict[str, tuple]:
    """Replay the traces off the chain, latest wins. A person changing their mind is the normal
    case on a design that is still being written, and the earlier trace stays in the record."""
    out: dict[str, tuple] = {}
    for e in entries:
        if e.get("action") == TRACED:
            out[e.get("task", "")] = tuple(e.get("objects") or ())
    return out


def _with_traces(spec: Specification, entries: list[dict]) -> Specification:
    traces = _traced(entries)
    return Specification(
        requirements=[Requirement(**{**r.__dict__, "objects": traces.get(r.req_id, r.objects)})
                      for r in spec.requirements],
        controls=spec.controls)


@router.post("")
def register(eid: str, body: SpecificationIn,
             identity: Identity = Depends(require("register_system"))):
    """Take the specification. Replaces it: a specification is a statement about now, and the
    traces already on the chain are replayed against whatever it now says."""
    e = get_or_404(eid)
    try:
        spec = Specification(
            requirements=[Requirement(**{k: (tuple(v) if k == "objects" else v)
                                         for k, v in r.items()
                                         if k in ("req_id", "requirement", "rationale",
                                                  "countries", "wave", "fit", "control",
                                                  "objects")}) for r in body.requirements],
            controls=[Control(**{k: v for k, v in c.items()
                                 if k in ("control_id", "objective", "owner", "frequency",
                                          "evidence")}) for c in body.controls])
    except (RequirementError, TypeError) as ex:
        raise HTTPException(422, str(ex)) from None

    _SPECS[eid] = spec
    e.ledger.append("SPECIFICATION", "SPEC_REGISTERED", identity.subject,
                    f"{len(spec.requirements)} requirement(s), {len(spec.controls)} control "
                    f"objective(s)", requirements=len(spec.requirements),
                    controls=len(spec.controls))
    return account(_with_traces(spec, e.ledger.entries), e.ir)


@router.get("")
def read(eid: str, identity: Identity = Depends(require("read"))):
    """The specification against signed intent. Read access on purpose: whether a programme is
    building what was asked for is not a privileged question."""
    e = get_or_404(eid)
    return account(_with_traces(_spec_or_404(eid), e.ledger.entries), e.ir)


@router.post("/requirements/{req_id}/trace")
def trace(eid: str, req_id: str, body: Trace,
          identity: Identity = Depends(require("ledger_append"))):
    """Say which configuration objects satisfy a requirement, under your own name.

    The objects need not exist yet. A requirement traced to an object nothing describes is reported
    as NOT_CONFIGURED, which is a true and useful answer — and far better than the requirement
    sitting untraceable because somebody waited for the build.
    """
    e = get_or_404(eid)
    spec = _spec_or_404(eid)
    if req_id not in {r.req_id for r in spec.requirements}:
        raise HTTPException(404, f"{req_id} is not a requirement of this specification.")
    objects = [o.strip() for o in body.objects if o.strip()]
    if not objects:
        raise HTTPException(
            422, f"Tracing {req_id} to nothing is what it already says. If no object satisfies it, "
                 f"that is a gap for the design authority to record, not a trace.")
    e.ledger.append(req_id, TRACED, identity.subject,
                    body.why or f"satisfied by {', '.join(objects)}", objects=objects)
    return account(_with_traces(spec, e.ledger.entries), e.ir)
