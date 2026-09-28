"""The engagement plan, registered and then run.

Absorbing a mobilisation pack produced a hundred tasks, thirteen gates with named approvers, fifteen
decisions on the critical path and eight boundary conditions. This is where they live and where they
are answered — and the rules are the ones the rest of the platform already uses, because a gate is
an approval and a condition is a claim somebody has to make under their own name.

Nothing here reports a percentage complete. A number made partly of tasks the platform cannot see
would be quoted as progress, and most of a programme's tasks are workshops.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.programme import (CONDITION_BREACHED, CONDITION_CONFIRMED, GATE_PASSED, TASK_DONE,
                                   Condition, Gate, Programme, ProgrammeError, Task, account)
from pydantic import BaseModel

from ..auth import Identity, require
from .engagements import get_or_404

router = APIRouter(prefix="/engagements/{eid}/programme", tags=["programme"])

#: The registers, per engagement. Declarations, not outcomes: everything that *happened* is on the
#: chain, which is why a restart loses the register and never the record of what was answered.
_PLANS: dict[str, Programme] = {}


class ProgrammeIn(BaseModel):
    conditions: list[dict] = []
    gates: list[dict] = []
    tasks: list[dict] = []


class Evidence(BaseModel):
    evidence: str
    #: For a gate: the person the pack names as its approver. Recorded beside the authenticated
    #: actor, because a plan names an approver and a token proves who pressed the button.
    on_behalf_of: str = ""


def _plan_or_404(eid: str) -> Programme:
    plan = _PLANS.get(eid)
    if plan is None:
        raise HTTPException(404, "No programme has been absorbed for this engagement. Register the "
                                 "plan of record's conditions, gates and tasks first — a programme "
                                 "the platform has not been given is not a programme with nothing "
                                 "in it.")
    return plan


@router.post("")
def register(eid: str, body: ProgrammeIn,
             identity: Identity = Depends(require("register_system"))):
    """Take the plan of record. Replaces the register: a plan is a statement about now."""
    e = get_or_404(eid)
    try:
        plan = Programme(
            conditions=[Condition(**{k: v for k, v in c.items()
                                     if k in ("what", "by", "consequence")}) for c in body.conditions],
            gates=[Gate(**{k: v for k, v in g.items()
                           if k in ("gate_id", "name", "date", "due_on", "criteria", "evidence",
                                    "approver")}) for g in body.gates],
            tasks=[Task(**{k: (tuple(v) if k == "depends_on" else v) for k, v in t.items()
                           if k in ("task_id", "task", "week", "owner", "due", "gate",
                                    "depends_on", "declared_status", "watches")})
                   for t in body.tasks])
    except (ProgrammeError, TypeError) as ex:
        raise HTTPException(422, str(ex)) from None

    _PLANS[eid] = plan
    e.ledger.append("PROGRAMME", "PLAN_REGISTERED", identity.subject,
                    f"{len(plan.tasks)} task(s), {len(plan.gates)} gate(s), "
                    f"{len(plan.conditions)} boundary condition(s)",
                    tasks=len(plan.tasks), gates=len(plan.gates), conditions=len(plan.conditions))
    return account(plan, e.ledger.entries)


@router.get("")
def read(eid: str, today: str = "", identity: Identity = Depends(require("read"))):
    """The programme against the chain. `today` as ISO, for lateness; omitted, none is claimed."""
    e = get_or_404(eid)
    return account(_plan_or_404(eid), e.ledger.entries, today)


@router.post("/conditions/confirm")
def confirm_condition(eid: str, what: str, body: Evidence,
                      identity: Identity = Depends(require("ledger_append"))):
    """Somebody says a boundary condition holds, under their own name and with what they checked."""
    e = get_or_404(eid)
    plan = _plan_or_404(eid)
    if what not in {c.what for c in plan.conditions}:
        raise HTTPException(404, f"{what!r} is not a boundary condition of this programme.")
    if not body.evidence.strip():
        raise HTTPException(422, "A condition is confirmed against something. Without evidence it "
                                 "is somebody's impression, and the consequence of it failing is "
                                 "already written down.")
    e.ledger.append(what, CONDITION_CONFIRMED, identity.subject, body.evidence)
    return account(plan, e.ledger.entries)


@router.post("/conditions/breach")
def breach_condition(eid: str, what: str, body: Evidence,
                     identity: Identity = Depends(require("ledger_append"))):
    """It has failed. The consequence the pack wrote down is what happens next, and it is quoted."""
    e = get_or_404(eid)
    plan = _plan_or_404(eid)
    condition = next((c for c in plan.conditions if c.what == what), None)
    if condition is None:
        raise HTTPException(404, f"{what!r} is not a boundary condition of this programme.")
    e.ledger.append(what, CONDITION_BREACHED, identity.subject,
                    body.evidence or "breached", consequence=condition.consequence)
    return account(plan, e.ledger.entries)


@router.post("/gates/{gate_id}/pass")
def pass_gate(eid: str, gate_id: str, body: Evidence,
              identity: Identity = Depends(require("approve"))):
    """A gate passes on evidence, by somebody who did not do the work.

    `approve`, because that is what a gate is. The evidence is required and recorded: a gate whose
    criteria were met and whose evidence nobody wrote down is a date that passed.
    """
    e = get_or_404(eid)
    plan = _plan_or_404(eid)
    gate = next((g for g in plan.gates if g.gate_id == gate_id), None)
    if gate is None:
        raise HTTPException(404, f"{gate_id} is not a gate of this programme.")
    if not body.evidence.strip():
        raise HTTPException(
            422, f"{gate_id} passes on evidence. The pack says what it needs: {gate.evidence}")

    # The tasks this gate covers, and whether the platform saw them done. It cannot see a workshop,
    # and it says so rather than blocking on something it has no view of.
    state = {t["task_id"]: t for t in account(plan, e.ledger.entries)["tasks"]}
    mine = [t for t in state.values() if t["gate"] == gate_id]
    visible_undone = [t["task_id"] for t in mine if t["visible_to_platform"] and not t["done"]]
    if visible_undone:
        raise HTTPException(
            409, f"{gate_id} covers {', '.join(visible_undone)}, which the platform can see and "
                 f"which are not done. A gate that passed over work the chain says is outstanding "
                 f"would be a date, not a gate.")

    e.ledger.append(gate_id, GATE_PASSED, identity.subject, body.evidence,
                    named_approver=gate.approver, on_behalf_of=body.on_behalf_of,
                    tasks_not_visible=sum(1 for t in mine if not t["visible_to_platform"]))
    return account(plan, e.ledger.entries)


@router.post("/tasks/{task_id}/done")
def task_done(eid: str, task_id: str, body: Evidence,
              identity: Identity = Depends(require("ledger_append"))):
    """A task the platform cannot see, reported done by a person under their own name.

    Never for a task that watches something: where the chain can answer, a person asserting it
    would be an attestation standing in for evidence that exists.
    """
    e = get_or_404(eid)
    plan = _plan_or_404(eid)
    task = next((t for t in plan.tasks if t.task_id == task_id), None)
    if task is None:
        raise HTTPException(404, f"{task_id} is not a task of this programme.")
    if task.watches:
        raise HTTPException(
            409, f"{task_id} watches {task.watches}, so the chain answers whether it is done. A "
                 f"person asserting it would stand in for evidence the platform already has.")
    e.ledger.append(task_id, TASK_DONE, identity.subject, body.evidence or "reported done")
    return account(plan, e.ledger.entries)
