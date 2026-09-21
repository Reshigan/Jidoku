"""The night shift, and the handover it leaves for the morning.

M1 of the team-member model: a tool has sessions, a colleague has a working day. The night shift
does what needs no person — read the systems, check signed intent against them, chase what was
handed over, re-score the twin, run the controls — and the morning opens with a handover in first
person, in three parts: what I did, what I found, what I need from you today.

M3 is the part that makes it a colleague rather than a firehose. Everything the night finds is
ranked by **cost of silence**: what it costs the programme if this goes unsaid until tomorrow.
A chain break or a statutory block earns an interruption now; everything else accumulates into
the handover and waits for the morning. The interruption budget is hard, and an unspent budget
stays unspent — a colleague who talks less than they could is trusted more.

The scheduler in `scheduler.py` has held the shift clock and the budget since the first commit
with nothing to schedule. This is the work it schedules.

Pure over its inputs: the night's findings arrive as data, and what comes back is a plan of what
to say and a handover to say it in. Nothing here reads a system or writes a ledger.
"""
from dataclasses import dataclass, field
from datetime import datetime

from .people import Ask, Person, route
from .scheduler import Scheduler, Shift

#: What a finding costs if nobody hears it until tomorrow. Published, because the whole point of
#: a budget is that the ranking can be argued with rather than felt.
COST_OF_SILENCE = {
    "chain_broken": 100,        # every statement on the ledger is unproven until this is answered
    "partial_write": 90,        # a customer's system is in a state nobody designed
    "control_failing": 70,      # a control that held yesterday does not hold today
    "statutory_open": 60,       # a value nobody may guess is blocking the plan
    "drift": 50,                # the live system disagrees with signed intent
    "arming_lapsed": 30,        # work stopped because an approval window closed
    "awaiting_person": 20,      # somebody's manual step is outstanding
    "unconfirmable": 15,        # nothing can check it and nobody has attested
    "twin_miss": 10,            # the twin was wrong; worth knowing, worth nobody's night
}

#: Above this, a finding is worth waking somebody for. Below it, the morning is soon enough.
INTERRUPT_ABOVE = 55


@dataclass
class Finding:
    kind: str
    what: str
    #: The role to name when nobody is registered who could answer it. Honest and useless on its
    #: own — a request addressed to nobody is a request nobody answers — which is what `needs` and
    #: a registered team fix (M4).
    who: str = ""
    detail: str = ""
    #: The permission it takes to answer this, as the platform's own role table spells it.
    needs: str = ""

    @property
    def cost(self) -> int:
        return COST_OF_SILENCE.get(self.kind, 0)


@dataclass
class Night:
    """One night's work: what was done, what it found, and what the morning is owed."""
    did: list = field(default_factory=list)
    findings: list = field(default_factory=list)


def run(night: Night, *, budget: int = 3, interrupt_above: int = INTERRUPT_ABOVE,
        people: list[Person] | None = None, now: datetime | None = None) -> dict:
    """Rank the night's findings, spend the interruption budget, leave the rest for the morning.

    The budget is spent on cost, not on order of discovery — a chain break found at 04:00 outranks
    a stale attestation found at 22:00, and a night that finds four urgent things still only
    interrupts three times and says so in the handover rather than quietly dropping the fourth.
    """
    scheduler = Scheduler(interruption_budget=budget)
    for f in sorted(night.findings, key=lambda f: -f.cost):
        scheduler.submit(f.what, cost_of_silence=f.cost, shift=Shift.NIGHT,
                         interrupts_human=f.cost >= interrupt_above)
    ran = scheduler.run(Shift.NIGHT)
    interrupted = [t.name for t in ran if t.interrupts_human]
    by_name = {f.what: f for f in night.findings}

    def rows(names):
        return [_routed(by_name[n], people, now, interrupt_above) for n in names if n in by_name]

    return {"did": list(night.did),
            "interrupted": rows(interrupted),
            "deferred": rows(scheduler.handover()["deferred"]),
            "waited": rows([t.name for t in ran if not t.interrupts_human]),
            "budget": {"of": budget, "spent": len(interrupted),
                       "held_back": len(scheduler.handover()["deferred"]),
                       "threshold": interrupt_above},
            "cost_of_silence": dict(COST_OF_SILENCE)}


def _finding_dict(f: Finding) -> dict:
    return {"kind": f.kind, "what": f.what, "who": f.who, "detail": f.detail, "cost": f.cost,
            "needs": f.needs, "when": "", "why": ""}


def _routed(f: Finding, people, now, interrupt_above: int) -> dict:
    """Put a name to it where one is registered, and keep the role where none is.

    Routing never invents a person. With no team registered the handover says what it always
    said — a role — and says it without pretending that is the same thing as asking somebody.
    """
    out = _finding_dict(f)
    if not people or not f.needs:
        return out
    r = route(Ask(f.what, f.needs, f.cost, f.detail), people, now, interrupt_above)
    if r.person is None:
        return {**out, "why": r.why}
    return {**out, "who": r.person.name, "when": r.when, "why": r.why}


def compose(night: dict, engagement: str, client: str) -> str:
    """The handover, in first person, in three parts. The one artefact nobody else can write.

    First person because a handover written in the third person is a status report, and nobody
    reads those. Short because it is read at 08:00 with a coffee, not filed.
    """
    lines = [f"Handover — {client}, {engagement}", ""]

    lines.append("**What I did**")
    lines += [f"- {d}" for d in night["did"]] or ["- Nothing needed doing overnight."]
    lines.append("")

    found = night["interrupted"] + night["waited"] + night["deferred"]
    lines.append("**What I found**")
    if not found:
        lines.append("- Nothing. Every check I ran came back the way it did yesterday.")
    else:
        for f in found:
            lines.append(f"- {f['what']}" + (f" — {f['detail']}" if f["detail"] else ""))
    lines.append("")

    lines.append("**What I need from you today**")
    asks = [f for f in found if f["who"]]
    if not asks:
        lines.append("- Nothing from me. I will keep checking.")
    else:
        for f in asks:
            when = f.get("when")
            lines.append(f"- {f['who']}{' — ' + when if when and when != 'now' else ''}: "
                         f"{f['what']}")
    unaddressed = [f for f in found if not f["who"] and f.get("why")]
    for f in unaddressed:
        # Nobody registered can answer it. Say that plainly rather than dropping it: an ask with
        # no owner is the finding.
        lines.append(f"- (nobody I can ask) {f['what']} — {f['why']}")
    lines.append("")

    spent, of = night["budget"]["spent"], night["budget"]["of"]
    if night["budget"]["held_back"]:
        lines.append(f"*I woke somebody {spent} time{'' if spent == 1 else 's'} of {of} allowed "
                     f"and held {night['budget']['held_back']} back for this note — they were "
                     f"urgent, and there is a limit to how often I am willing to be the reason "
                     f"somebody's night ended.*")
    elif spent:
        lines.append(f"*I woke somebody {spent} time{'' if spent == 1 else 's'} of {of} allowed. "
                     f"Everything else is above.*")
    else:
        lines.append("*I did not wake anybody. Nothing overnight was worth it.*")
    return "\n".join(lines)
