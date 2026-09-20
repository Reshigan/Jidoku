"""The crew run: a team of consultants takes the engagement as far as it can go alone.

This is where the Agent OS stops being a diagram. `jidoka_os` has held rings, capabilities, a
syscall table and an economy of five agents since the first commit, and `Kernel.register` had no
caller anywhere — a kernel with no handlers is a security model nobody can run. This module is
the handler table: the one place where an agent's syscall becomes a real read of a customer's
system, a real dry run through the executor, a real decision point on the ledger.

Every handler is the same code path the console's own buttons use. That is deliberate and it is
the whole safety argument: the crew does not get a faster, looser route to a customer's systems
because it is a machine. It gets the operator's route, through the executor, with the registry,
the ledger, the arming gate and the snapshot gate all in front of it — and with less authority,
because no ring an agent can occupy holds APPROVE.

So an unattended run ends in a handover, never a fait accompli. It sequences the work, snapshots,
rehearses every Tier-A write as a dry run, emits the Tier-B and Tier-C artefacts a person must
execute by hand, raises the statutory questions nobody may guess, objects to its own output from
a ring that cannot write, prices what is left, and verifies. Arming and approval stay human.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.planner import PlanError, plan as build_plan
from jidoka_core.registry import RegistryError, WriteLockViolation
from jidoka_os import crew
from jidoka_os.economy import MessageBus
from jidoka_os.process import Supervisor
from jidoka_os.syscalls import Kernel

from ..auth import Identity, require
from .engagements import get_or_404
from .execution import _adapter_for, _executor, _record_or_404
from .verification import run_verification

router = APIRouter(prefix="/engagements/{eid}/run", tags=["run"])

# eid -> the last run's report. Process memory, like armings: a report is a reading of a moment,
# and the ledger holds what actually happened. A restart loses the summary, never the evidence.
_RUNS: dict[str, dict] = {}


class PlanBlocked(Exception):
    """The planner refusing, carried across the syscall boundary as the refusal a person reads."""


def _handlers(e, identity: Identity, kernel: Kernel) -> None:
    """Bind every syscall the crew can make to the code the console's buttons already call."""
    ex = _executor(e, identity)

    def sys_plan(proc, **_):
        try:
            return build_plan(e.ir, {**e.open_dps, **e.decisions.unresolved()})
        except PlanError as err:
            raise PlanBlocked(str(err))

    def sys_extract(proc, key: str = "", **_):
        """A snapshot. The executor writes the SNAPSHOT entry, so invariant 4's precondition is
        established by reading the system rather than by anybody saying they did."""
        rec = _record_or_404(e, key)
        system = e.registry.get(rec.system_binding)
        rows = ex.snapshot(key, _adapter_for(rec.product, e.connectors.get(rec.system_binding)),
                           rec, system)
        return {"key": key, "rows": len(rows)}

    def sys_write_tier_a(proc, key: str = "", **_):
        """A rehearsal, always. `armed=None` is what makes it one: the executor's own gate turns
        an unarmed Tier-A step into a dry run, and there is no argument from here that changes it
        (invariant 6). The crew cannot arm, because no agent ring holds the authority to."""
        rec = _record_or_404(e, key)
        res = ex.execute(key, _adapter_for(rec.product, e.connectors.get(rec.system_binding)),
                         rec, armed=None)
        return {"key": res.key, "tier": res.tier, "system": res.system, "status": res.status,
                "detail": res.detail, "payload": res.payload}

    def sys_emit_artefact(proc, key: str = "", **_):
        """Tier B and C: the executor hands off to a person and ledgers that it did."""
        rec = _record_or_404(e, key)
        res = ex.execute(key, _adapter_for(rec.product, e.connectors.get(rec.system_binding)), rec)
        return res.payload

    def sys_raise_dp(proc, dp_id: str = "", dp_type: str = "DESIGN", question: str = "",
                     owner: str = "", **_):
        from jidoka_core.decisions import DecisionPoint

        dp = e.decisions.raise_dp(DecisionPoint(dp_id, dp_type, question, owner))
        e.persist_dps()
        return {"dp_id": dp.dp_id}

    def sys_ledger_append(proc, task: str = "", action: str = "", detail: str = "", **_):
        return e.ledger.append(task, action, proc.manifest.name, detail)

    def sys_halt(proc, reason: str = "", by: str = "", **_):
        kernel.halt(reason, by or proc.manifest.name)
        return {"halted": True, "reason": reason}

    for name, fn in (("sys_plan", sys_plan), ("sys_extract", sys_extract),
                     ("sys_write_tier_a", sys_write_tier_a),
                     ("sys_emit_artefact", sys_emit_artefact), ("sys_raise_dp", sys_raise_dp),
                     ("sys_ledger_append", sys_ledger_append), ("sys_halt", sys_halt)):
        kernel.register(name, fn)
    # sys_ledger_approve and sys_resolve_dp are deliberately not registered. Their capabilities
    # exist in no ring an agent can occupy, so a handler for either would be unreachable code
    # that looks like a door — and one refactor away from being one.


@router.post("")
def start(eid: str, identity: Identity = Depends(require("execute"))):
    """Run the crew. Gated on `execute` because that is what it does — the builder's authority and
    not one permission more. An approver cannot start a run, because `execute` is not theirs."""
    e = get_or_404(eid)
    if not e.ir:
        raise HTTPException(409, "This engagement holds no signed intent, so there is nothing to "
                                 "run. Load a workbook, or read a live system under Insight.")
    supervisor = Supervisor(e.ledger)
    kernel = Kernel(e.ledger, e.registry, supervisor)
    _handlers(e, identity, kernel)

    try:
        report = crew.run(
            kernel,
            records=list(e.ir),
            open_dp_ids=set(e.decisions.dps),
            actor=identity.subject,
            bus=MessageBus(e.ledger),
            verify=lambda: run_verification(e, identity.subject),
        )
    except (RegistryError, WriteLockViolation) as err:
        # The landscape refusing is a finding about the engagement, not a server fault.
        raise HTTPException(409, str(err))

    e.ledger.append("RUN", "CREW_RUN", identity.subject,
                    f"{len(report['steps'])} step(s) rehearsed, "
                    f"{len(report['artefacts'])} artefact(s) emitted, "
                    f"{len(report['decisions_raised'])} question(s) raised, "
                    f"{len(report['waiting_on_a_person'])} item(s) waiting on a person",
                    rehearsed=len(report["steps"]), raised=len(report["decisions_raised"]))
    _RUNS[eid] = report
    return report


@router.get("")
def last(eid: str, identity: Identity = Depends(require("read"))):
    """The last run in this process, or nothing. Never a cached claim about a live system: an
    empty answer is the honest one until somebody runs the crew."""
    get_or_404(eid)
    return _RUNS.get(eid) or {"crew": [], "plan": None, "plan_blocked": None, "steps": [],
                              "artefacts": [], "decisions_raised": [], "objections": [],
                              "economics": None, "verification": None,
                              "waiting_on_a_person": [], "halted": False, "halt_reason": ""}
