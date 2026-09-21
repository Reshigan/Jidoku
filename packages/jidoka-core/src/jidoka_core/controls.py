"""Controls as executable predicates over the ledger, tested against the whole population.

A control is normally prose in a binder, and evidence is assembled toward it once a year by
somebody sampling forty rows out of eleven thousand. Invert it: write the control as a predicate,
run it over every row the ledger holds, and the same artefact serves design, testing, monitoring
and the audit file at once. A failure is a lamp on the board the day it happens rather than a
finding six months later (C6).

Two properties make this worth doing here rather than anywhere else, and both come from the
chain. The population is complete — every act that touched a customer's system is on it, or the
act did not happen through this platform at all. And the evidence for a passing control is the
same shape as the evidence for a failing one: the rows themselves, enumerated, never counted.

So every control returns its violations in full. There is no sampling, no "3 exceptions found",
no top-ten truncation. A control that cannot show you its violations is prose again.

Pure stdlib, pure over its inputs. The ledger goes in, findings come out, and nothing here writes.
"""
from dataclasses import dataclass, field
from typing import Callable

#: Ledger actions that changed a customer's system. The population every write control runs over.
WRITES = ("EXECUTED", "ROLLED_BACK", "TRANSPORT_ADVANCED")


@dataclass(frozen=True)
class Finding:
    """One row that fails a control. Carries enough to act on without opening the ledger."""
    task: str
    actor: str
    ts: str
    why: str

    def as_dict(self) -> dict:
        return {"task": self.task, "actor": self.actor, "ts": self.ts, "why": self.why}


@dataclass(frozen=True)
class Control:
    control_id: str
    statement: str            # what must be true, in one sentence a non-engineer can check
    predicate: Callable       # (entries, context) -> list[Finding]
    population: str           # what it runs over, so a pass means something specific
    rows: Callable = None     # (entries) -> the rows this control tested

    def run(self, entries: list[dict], context: dict | None = None) -> dict:
        violations = self.predicate(entries, context or {})
        tested = len(self.rows(entries))
        return {"control_id": self.control_id, "statement": self.statement,
                "population": self.population, "tested": tested,
                "passed": not violations, "violations": [v.as_dict() for v in violations],
                # Said explicitly: a control with nothing to test has not passed, it has not run.
                "status": "PASS" if (tested and not violations) else
                          "FAIL" if violations else "NOT_EXERCISED"}


def _by_action(entries, *actions) -> list[dict]:
    return [e for e in entries if e.get("action") in actions]


# --- the controls ---------------------------------------------------------------------------------

def _writes_have_a_prior_snapshot(entries, _ctx) -> list[Finding]:
    out = []
    for i, e in enumerate(_index(entries, "EXECUTED")):
        entry, at = e
        if not any(x.get("action") == "SNAPSHOT" and x.get("task") == entry.get("task")
                   for x in entries[:at]):
            out.append(Finding(entry.get("task", ""), entry.get("actor", ""), entry.get("ts", ""),
                               "written with no before-state on the chain"))
    return out


def _approvals_are_not_self_approvals(entries, _ctx) -> list[Finding]:
    out = []
    for entry, at in _index(entries, "APPROVED"):
        builders = {x.get("actor") for x in entries[:at]
                    if x.get("task") == entry.get("task") and x.get("action") == "EXECUTED"}
        if entry.get("actor") in builders:
            out.append(Finding(entry.get("task", ""), entry.get("actor", ""), entry.get("ts", ""),
                               "approved by the person who executed it"))
    return out


def _live_writes_were_armed_by_someone_else(entries, _ctx) -> list[Finding]:
    out = []
    for entry, _ in _index(entries, "EXECUTED"):
        armed_by = entry.get("armed_by")
        if not armed_by:
            out.append(Finding(entry.get("task", ""), entry.get("actor", ""), entry.get("ts", ""),
                               "live write with no armed target recorded"))
        elif armed_by == entry.get("actor"):
            out.append(Finding(entry.get("task", ""), entry.get("actor", ""), entry.get("ts", ""),
                               f"armed and executed by the same person ({armed_by})"))
    return out


def _one_way_decisions_carry_two_approvers(entries, _ctx) -> list[Finding]:
    out = []
    for entry, _ in _index(entries, "DP_RESOLVED"):
        second = entry.get("second_approver")
        if "ONE_WAY" in str(entry.get("detail", "")) and not second:
            out.append(Finding(entry.get("task", ""), entry.get("actor", ""), entry.get("ts", ""),
                               "one-way decision resolved by a single approver"))
    return out


def _nothing_was_written_to_a_read_only_system(entries, ctx) -> list[Finding]:
    write_locked = ctx.get("write_locked") or set()
    out = []
    for entry, _ in _index(entries, *WRITES):
        system = entry.get("system") or entry.get("target_system") or ""
        if system in write_locked:
            out.append(Finding(entry.get("task", ""), entry.get("actor", ""), entry.get("ts", ""),
                               f"a write reached {system}, which may not hold write credentials"))
    return out


def _transports_landed_in_production(entries, _ctx) -> list[Finding]:
    """Not a gate — a standing question. An ABAP change that stopped in QA is unfinished work,
    and unfinished work that nobody is looking at is how a cutover discovers itself (ADR-0006)."""
    landed, out = {}, []
    for entry, _ in _index(entries, "TRANSPORT_ADVANCED"):
        landed[entry.get("request_id")] = entry
    for request_id, entry in landed.items():
        if not entry.get("in_production"):
            out.append(Finding(entry.get("task", ""), entry.get("actor", ""), entry.get("ts", ""),
                               f"{request_id} stopped at {entry.get('target_system')}; "
                               f"next hop {entry.get('next_hop')}"))
    return out


def _index(entries, *actions):
    """(entry, position) for each matching row. Position matters: half these controls ask whether
    something was already on the chain when the row was written, and "already" is an index."""
    return [(e, i) for i, e in enumerate(entries) if e.get("action") in actions]


CONTROLS: dict[str, Control] = {}


def _register(control_id, statement, predicate, population, rows):
    CONTROLS[control_id] = Control(control_id, statement, predicate, population, rows)


_register("C-EXE-01",
          "Every live write was preceded by a snapshot of the state it replaced.",
          _writes_have_a_prior_snapshot,
          "every EXECUTED entry on the chain",
          lambda entries: _by_action(entries, "EXECUTED"))

_register("C-SOD-01",
          "No approval was given by the person who performed the work.",
          _approvals_are_not_self_approvals,
          "every APPROVED entry on the chain",
          lambda entries: _by_action(entries, "APPROVED"))

_register("C-ARM-01",
          "Every live write was armed by somebody other than the person who spent the arming.",
          _live_writes_were_armed_by_someone_else,
          "every EXECUTED entry on the chain",
          lambda entries: _by_action(entries, "EXECUTED"))

_register("C-DEC-01",
          "Every one-way decision was resolved by two distinct named approvers.",
          _one_way_decisions_carry_two_approvers,
          "every resolved decision point",
          lambda entries: _by_action(entries, "DP_RESOLVED"))

_register("C-TRN-01",
          "Every released transport reached production.",
          _transports_landed_in_production,
          "every transport that moved at least one hop",
          lambda entries: _by_action(entries, "TRANSPORT_ADVANCED"))

_register("C-REG-01",
          "No write of any kind reached a system that may not hold write credentials.",
          _nothing_was_written_to_a_read_only_system,
          "every write on the chain",
          lambda entries: _by_action(entries, *WRITES))


def run_all(entries: list[dict], write_locked: set | None = None) -> dict:
    """Every control, over the whole population, with violations enumerated in full.

    `write_locked` is the set of system_ids the registry forbids writes to. It comes from the
    caller because the registry is the authority on roles and this module is the authority on
    nothing — a control that decided for itself which systems were read-only would be checking
    its own opinion.
    """
    results = [c.run(entries, {"write_locked": write_locked or set()})
               for c in CONTROLS.values()]
    return {"controls": sorted(results, key=lambda r: r["control_id"]),
            "failing": sorted(r["control_id"] for r in results if r["status"] == "FAIL"),
            "not_exercised": sorted(r["control_id"] for r in results
                                    if r["status"] == "NOT_EXERCISED"),
            "population_complete": True,
            "method": ("Each control is a predicate over the engagement's whole ledger. Every row "
                       "is tested, never a sample, and every violation is listed rather than "
                       "counted — a control that cannot show its violations is prose again.")}
