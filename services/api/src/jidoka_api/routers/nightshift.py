"""The night shift: the work that needs no person, and the handover it leaves.

Everything here already exists somewhere else — verification, the controls, the twin's fidelity,
the chain, the armings. The night shift is not a new capability, it is the decision to run them
while nobody is watching and to arrive in the morning with the work started (M1, M2).

What it adds is restraint. Every finding is ranked by cost of silence and the interruption budget
is hard, so a chain break earns a wake-up and a stale attestation waits for the handover. An
unspent budget stays unspent.
"""
from fastapi import APIRouter, Depends, HTTPException
from jidoka_core.controls import run_all
from jidoka_core.objections import due
from jidoka_core.twin import fidelity
from jidoka_os.handover import (CADENCE_ACTION, DEFAULT_CADENCE_HOURS, FAILED_ACTION,
                                Finding, Night, cadence, clock, compose,
                                run as run_night)
from jidoka_os.people import ASKED, asked_this_week, load as load_people, observed_latency, \
    week_start

from ..auth import Identity, require
from .engagements import get_or_404
from .execution import _ARMED
from .verification import run_verification

router = APIRouter(prefix="/engagements/{eid}/nightshift", tags=["nightshift"])

_NIGHTS: dict[str, dict] = {}


def _findings(e, verification: dict, controls: dict) -> list[Finding]:
    """Everything the night turned up, each one already knowing what it costs to stay quiet."""
    out = []

    try:
        e.ledger.verify_chain()
    except Exception as ex:                      # noqa: BLE001 — a raising chain is a broken one
        out.append(Finding("chain_broken", "the ledger chain does not verify",
                           "whoever can clear a halt", type(ex).__name__, needs="halt"))

    # A half-landed write that was never put back. The rollback the crew would have attempted
    # leaves its own entry, so an unmatched PARTIAL is one nobody has dealt with.
    undone = {x.get("task") for x in e.ledger.entries if x.get("action") == "ROLLED_BACK"}
    for entry in e.ledger.entries:
        if entry.get("action") == "PARTIAL" and entry.get("task") not in undone:
            out.append(Finding("partial_write",
                               f"{entry.get('task')} half-landed and was never put back",
                               "an operator", entry.get("detail", ""), needs="execute"))

    for control_id in controls["failing"]:
        result = next(c for c in controls["controls"] if c["control_id"] == control_id)
        out.append(Finding("control_failing", f"{control_id} is failing: {result['statement']}",
                           "whoever owns this control",
                           f"{len(result['violations'])} violation(s) over {result['tested']} tested",
                           needs="approve"))

    for dp in e.decisions.dps.values():
        if dp.resolution is None and dp.dp_type == "STATUTORY":
            out.append(Finding("statutory_open", f"{dp.dp_id} is blocking the plan", dp.owner,
                               dp.question, needs="resolve_dp"))

    for finding in verification["drift"]:
        out.append(Finding("drift", f"{finding['key']} no longer matches signed intent",
                           "whoever signed it", finding.get("decision_point", ""),
                           needs="resolve_dp"))
    for item in verification["awaiting_a_person"]:
        out.append(Finding("awaiting_person", f"{item['key']} is still not in the system",
                           "a consultant at the keyboard",
                           f"handed over {item.get('handed_over', '')}".strip(), needs="execute"))
    for item in verification["unconfirmable"]:
        out.append(Finding("unconfirmable", f"{item['key']} cannot be checked and nobody has attested",
                           "whoever makes the change", item["reason"], needs="execute"))

    for (e_id, system_id), target in _ARMED.items():
        if e_id == e.engagement_id and target.expired():
            out.append(Finding("arming_lapsed", f"the arming of {system_id} has lapsed",
                               target.armed_by, "work against it is back to rehearsal",
                               needs="arm"))

    # The loop closing is what makes the next objection worth hearing (M6, ADR-0033). The night
    # is where it closes: an objection somebody set aside, at the phase where the thing it
    # predicted becomes observable, with what the chain says actually happened.
    for o in due(e.ledger.entries, e.phase):
        out.append(Finding("objection_due",
                           f"{o['objection_id']} is due a revisit: {o['finding']} on {o['about']}",
                           o["overridden_by"],
                           f"set aside by {o['overridden_by']} — {o['override_reason']}. It said: "
                           f"{o['consequence']}",
                           needs="approve"))

    for miss in fidelity(e.ledger.entries)["misses"]:
        out.append(Finding("twin_miss",
                           f"the twin predicted {miss['predicted']} for {miss['task']} and the "
                           f"system said {miss['outcome']}", "", "logged against the twin, not you"))
    return out


def _record_asks(e, out: dict, people, actor: str) -> None:
    """Put this night's asks on the ledger, so next week's capacity knows about this week's.

    Only asks that reached a registered person: a finding that named a role was addressed to
    nobody and consumed nobody's week. Only ones not already recorded this week, because the same
    unanswered question found on five consecutive nights is one thing that person owes.
    """
    names = {p.name for p in people}
    since = week_start()
    already = {(x.get("person"), x.get("detail")) for x in e.ledger.entries
               if x.get("action") == ASKED and x.get("ts", "") >= since}
    for row in out["interrupted"] + out["deferred"] + out["waited"]:
        if row["who"] in names and (row["who"], row["what"]) not in already:
            e.ledger.append(row["kind"], ASKED, actor, row["what"], person=row["who"])
            already.add((row["who"], row["what"]))


@router.post("")
def nightshift(eid: str, budget: int = 3, identity: Identity = Depends(require("ledger_append"))):
    """Work the night, then compose the morning's handover.

    A run that raises writes that it raised before it propagates. Otherwise a night that started
    and died halfway is indistinguishable from a clock that never fired, and the two have
    different fixes — one is a fault in the run, the other is a deployment nobody finished.
    """
    e = get_or_404(eid)
    try:
        return _work(e, budget, identity)
    except Exception as ex:                  # noqa: BLE001 — the failure is the thing to record
        # The class, never the message: an exception string can carry a DSN or a bearer.
        e.ledger.append("NIGHTSHIFT", FAILED_ACTION, identity.subject, type(ex).__name__)
        raise


def _work(e, budget: int, identity: Identity) -> dict:
    verification = run_verification(e, identity.subject)
    from jidoka_core.registry import WRITE_FORBIDDEN_ROLES

    locked = {s["system_id"] for s in e.registry.landscape()["systems"]
              if s["role"] in WRITE_FORBIDDEN_ROLES}
    controls = run_all(e.ledger.entries, write_locked=locked)

    # Every record the pass reached a verdict on, including the ones whose verdict was that
    # nothing can check them. Counting only the readable ones would overstate the night's reach.
    checked = sum(len(verification[k]) for k in
                  ("verified", "drift", "not_applied", "awaiting_a_person", "unconfirmable",
                   "attested"))
    night = Night(
        did=[f"checked {checked} record(s) against the systems they bind to",
             f"ran {len(controls['controls'])} control(s) over {len(e.ledger.entries)} ledger entries",
             "re-scored every twin prediction the systems have since answered"],
        findings=_findings(e, verification, controls))

    # With a team registered the handover addresses people by name, asks the least senior person
    # who may actually sign the thing with capacity left this week, and respects their clock
    # (M4, ADR-0029). With none, it names a role exactly as it did before rather than pretending
    # somebody was asked.
    people = load_people(e.people)
    out = run_night(night, budget=budget, people=people,
                    load=asked_this_week(e.ledger.entries),
                    latency=observed_latency(e.ledger.entries))
    _record_asks(e, out, people, identity.subject)
    out["handover"] = compose(out, e.name, e.client)
    e.ledger.append("NIGHTSHIFT", "HANDOVER", identity.subject,
                    f"{len(night.findings)} finding(s); woke somebody "
                    f"{out['budget']['spent']} time(s) of {budget}",
                    findings=len(night.findings), interrupted=out["budget"]["spent"])
    _NIGHTS[e.engagement_id] = out
    out["clock"] = clock(e.ledger.entries)
    return out


@router.post("/cadence")
def set_cadence(eid: str, hours: int = DEFAULT_CADENCE_HOURS,
                identity: Identity = Depends(require("ledger_append"))):
    """How often nights run here. Declared on the ledger rather than stored beside it: the clock
    reads the cadence and the runs off one chain, so there is no second copy to disagree."""
    e = get_or_404(eid)
    if hours < 1 or hours > 24 * 30:
        raise HTTPException(422, "A cadence is between 1 hour and 30 days. Outside that it is not "
                                 "a schedule, and a clock nobody believes is not a clock.")
    e.ledger.append("NIGHTSHIFT", CADENCE_ACTION, identity.subject,
                    f"nights run every {hours}h here", hours=hours)
    return {"every_hours": cadence(e.ledger.entries)}


@router.get("")
def last_night(eid: str, identity: Identity = Depends(require("read"))):
    """Last night's handover, or nothing — and whether the clock that runs them is still running.

    The handover itself is held in memory for the console to render, so a restart loses the text.
    Whether a night *happened* is a fact about the ledger, and the clock reads it there: every way
    the night stops is invisible from inside the night that did not run (ADR-0030).
    """
    e = get_or_404(eid)
    out = _NIGHTS.get(eid) or {"did": [], "interrupted": [], "deferred": [], "waited": [],
                               "budget": None, "handover": "", "cost_of_silence": {}}
    return {**out, "clock": clock(e.ledger.entries)}
