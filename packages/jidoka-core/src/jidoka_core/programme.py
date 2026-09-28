"""The engagement plan: conditions that must hold, gates that pass on evidence, tasks that are due.

Everything else in this kernel is about configuration. This is about the programme that produces
it, and it exists because a real mobilisation pack turned out to be a complete engagement machine
in spreadsheets: a hundred tasks with weeks and owners and dependencies, nineteen gates with
criteria and named approvers, twenty decisions on the critical path, eight boundary conditions with
a stated consequence each, and alignment rules whose "how it is checked" column said *configuration
extract* and whose "when" column said *G2 + nightly*. The platform was asked to absorb that, design
from it, and run it.

Three things, and the discipline is the same one the rest of the kernel uses: **derive what can be
derived, declare the rest, and never let a declaration look like a derivation.**

  **A condition holds or it does not, and a breach has a consequence somebody wrote down.**
  "Provisioning access by 1 Oct — Week 1 cannot start." A condition is not a risk register entry to
  be reviewed; it is a precondition with a named consequence, and the honest answer before anybody
  confirms it is *nobody has said*.

  **A gate passes on evidence, not on a date.** The criteria and the evidence are the pack's own
  words, the approver is a named person, and passing one is an approval on the chain under the same
  rule every other approval wears: not the person who did the work. A gate whose date has arrived
  and whose evidence has not is late, not passed.

  **A task's status is derived where the platform can see it and declared where it cannot.** "Take
  the baseline extract" is visible on the chain. "Run the Wednesday workshop" is not, and pretending
  otherwise would make the plan a place where progress is asserted — which is the thing this
  platform exists to stop.

Pure, stdlib, projections over declared rows and the chain.
"""
from dataclasses import dataclass, field

#: What the chain records about a programme. Declarations and outcomes, kept apart: the register is
#: what somebody said would happen, and these are what did.
CONDITION_CONFIRMED = "CONDITION_CONFIRMED"
CONDITION_BREACHED = "CONDITION_BREACHED"
GATE_PASSED = "GATE_PASSED"
TASK_DONE = "TASK_DONE"

#: A condition nobody has spoken about. Not "holding" — a precondition assumed to hold is how a
#: programme discovers on the Thursday that access was never granted.
UNSPOKEN = "nobody has said"


class ProgrammeError(Exception): ...


@dataclass(frozen=True)
class Condition:
    """A precondition with a consequence somebody wrote down."""
    what: str
    by: str = ""
    consequence: str = ""

    def __post_init__(self):
        if not self.what.strip():
            raise ProgrammeError("A condition with no statement cannot hold or fail.")
        if not self.consequence.strip():
            raise ProgrammeError(
                f"{self.what!r}: a condition states what happens if it fails. Without that it is a "
                f"hope, and a register of hopes is reviewed once and never again.")


@dataclass(frozen=True)
class Gate:
    """A gate passes on evidence. The date is when it is due, not when it passes."""
    gate_id: str
    name: str
    #: The pack's own words — "Fri 9 Oct". Kept verbatim, because that is what the approver reads.
    date: str = ""
    #: The same date as ISO, where whoever absorbed the pack could resolve one. Empty where they
    #: could not, and lateness is then not claimed rather than guessed: a gate register whose
    #: "late" column fires on a string comparison of prose would be wrong in both directions.
    due_on: str = ""
    criteria: str = ""
    evidence: str = ""
    approver: str = ""

    def __post_init__(self):
        if not self.criteria.strip() or not self.evidence.strip():
            raise ProgrammeError(
                f"{self.gate_id}: a gate names its criteria and the evidence that satisfies them. "
                f"A gate with neither passes on somebody's judgement of the date.")
        if not self.approver.strip():
            raise ProgrammeError(
                f"{self.gate_id}: a gate names the person who passes it. Without one the evidence "
                f"is filed and nobody has accepted it, which is a date rather than a gate.")


@dataclass(frozen=True)
class Task:
    task_id: str
    task: str
    week: str = ""
    owner: str = ""
    due: str = ""
    gate: str = ""
    depends_on: tuple = ()
    #: What the register says. Kept, and never confused with what the chain shows.
    declared_status: str = ""
    #: The ledger task this is visible as, where it is visible at all. Without one, the platform
    #: cannot see this task and says so rather than trusting the register.
    watches: str = ""


@dataclass
class Programme:
    conditions: list = field(default_factory=list)
    gates: list = field(default_factory=list)
    tasks: list = field(default_factory=list)


def condition_state(programme: Programme, entries: list[dict]) -> list[dict]:
    """Each condition, and what the chain says about it. Silence is reported as silence."""
    said = {}
    for e in entries:
        if e.get("action") in (CONDITION_CONFIRMED, CONDITION_BREACHED):
            said[e.get("task")] = e
    out = []
    for c in programme.conditions:
        entry = said.get(c.what)
        holding = (None if entry is None else entry["action"] == CONDITION_CONFIRMED)
        out.append({
            "what": c.what, "by": c.by, "consequence": c.consequence,
            "holding": holding,
            "who_said": entry.get("actor", "") if entry else "",
            "evidence": entry.get("detail", "") if entry else "",
            "says": (f"{c.what} — {UNSPOKEN}. If it fails: {c.consequence}" if holding is None
                     else f"{c.what} — confirmed by {entry.get('actor')}." if holding
                     else f"{c.what} — BREACHED. {c.consequence}")})
    return out


def gate_state(programme: Programme, entries: list[dict], today: str = "") -> list[dict]:
    """Each gate: passed on evidence by a named person, or not passed and possibly late.

    Reviewer != builder is the ledger's rule and it is not restated here. What this adds is that a
    gate passed by nobody is not passed, and a date that has arrived without evidence is late.
    """
    passed = {e.get("task"): e for e in entries if e.get("action") == GATE_PASSED}
    out = []
    for g in programme.gates:
        entry = passed.get(g.gate_id)
        late = bool(today and g.due_on and not entry and g.due_on < today)
        out.append({
            "gate_id": g.gate_id, "name": g.name, "date": g.date, "criteria": g.criteria,
            "evidence_required": g.evidence, "approver": g.approver,
            "passed": bool(entry), "passed_by": entry.get("actor", "") if entry else "",
            "passed_on": entry.get("ts", "") if entry else "",
            "evidence_given": entry.get("detail", "") if entry else "",
            "late": late,
            "due_on": g.due_on,
            "date_understood": bool(g.due_on),
            "says": (f"{g.gate_id} {g.name}: passed by {entry.get('actor')}." if entry
                     else f"{g.gate_id} {g.name}: due {g.date} and not passed. The evidence it "
                          f"needs is {g.evidence}." if late
                     else f"{g.gate_id} {g.name}: not yet passed. Due {g.date or 'unscheduled'}"
                          + ("" if g.due_on else ", and that date was not resolved to a day, so "
                                                 "lateness is not claimed for it") + ".")})
    return out


def task_state(programme: Programme, entries: list[dict]) -> list[dict]:
    """Each task, with what the chain shows kept apart from what the register claims."""
    done_on_chain = {e.get("task") for e in entries if e.get("action") == TASK_DONE}
    # Anything the platform actually did, by the ledger task it did it to.
    touched = {e.get("task") for e in entries
               if e.get("action") in ("EXECUTED", "VERIFIED", "HANDED_OFF", "APPROVED")}
    out = []
    for t in programme.tasks:
        seen = t.task_id in done_on_chain or (t.watches and t.watches in touched)
        out.append({
            "task_id": t.task_id, "task": t.task, "week": t.week, "owner": t.owner,
            "due": t.due, "gate": t.gate, "depends_on": list(t.depends_on),
            "declared_status": t.declared_status,
            "visible_to_platform": bool(t.watches),
            "done": bool(seen),
            "says": (f"{t.task_id}: done, on the chain." if seen
                     else f"{t.task_id}: the register says {t.declared_status!r} and the platform "
                          f"cannot see this task — it watches nothing."
                     if not t.watches
                     else f"{t.task_id}: not done. Watching {t.watches}.")})
    return out


def blocked(programme: Programme, entries: list[dict]) -> list[dict]:
    """Tasks whose dependencies are not done. The plan's own order, enforced."""
    states = {t["task_id"]: t for t in task_state(programme, entries)}
    out = []
    for t in states.values():
        waiting = [d for d in t["depends_on"] if d in states and not states[d]["done"]]
        if waiting and not t["done"]:
            out.append({**t, "waiting_on": waiting})
    return out


def account(programme: Programme, entries: list[dict], today: str = "") -> dict:
    """The programme, in one read. Nothing here is a percentage complete."""
    conds = condition_state(programme, entries)
    gates = gate_state(programme, entries, today)
    tasks = task_state(programme, entries)
    unspoken = [c for c in conds if c["holding"] is None]
    breached = [c for c in conds if c["holding"] is False]
    invisible = [t for t in tasks if not t["visible_to_platform"]]
    return {
        "conditions": conds, "gates": gates, "tasks": tasks,
        "blocked": blocked(programme, entries),
        "unspoken_conditions": len(unspoken), "breached_conditions": len(breached),
        "gates_passed": sum(1 for g in gates if g["passed"]),
        "gates_late": [g["gate_id"] for g in gates if g["late"]],
        "tasks_the_platform_cannot_see": len(invisible),
        "says": _says(conds, gates, tasks, unspoken, breached, invisible),
        "method": ("Conditions, gates and tasks as the programme declared them, against what the "
                   "chain shows. A task's completion is derived only where it watches something "
                   "the platform can see; everywhere else the register's claim is reported as the "
                   "register's claim. No percentage is published: a number made of tasks the "
                   "platform cannot see would be quoted as progress."),
    }


def _says(conds, gates, tasks, unspoken, breached, invisible) -> str:
    if breached:
        return (f"{len(breached)} boundary condition(s) have been breached: "
                + "; ".join(c["consequence"] for c in breached))
    parts = []
    if unspoken:
        parts.append(f"{len(unspoken)} of {len(conds)} boundary conditions are unconfirmed — "
                     f"nobody has said whether they hold")
    late = [g for g in gates if g["late"]]
    if late:
        parts.append(f"{len(late)} gate(s) are past their date without the evidence they need: "
                     + ", ".join(g["gate_id"] for g in late))
    if invisible:
        parts.append(f"{len(invisible)} of {len(tasks)} tasks are invisible to the platform, so "
                     f"their status is whatever the register says")
    if not parts:
        return (f"{sum(1 for g in gates if g['passed'])} of {len(gates)} gates passed on evidence; "
                f"every condition confirmed; every task the platform can see accounted for.")
    return ". ".join(parts) + "."
