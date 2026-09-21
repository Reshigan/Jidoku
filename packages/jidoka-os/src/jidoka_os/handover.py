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
from datetime import datetime, timezone

from .people import TS, Ask, Person, route
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
    "objection_due": 25,        # the platform said this would happen; it is time to look
    "twin_miss": 10,            # the twin was wrong; worth knowing, worth nobody's night
}

#: Above this, a finding is worth waking somebody for. Below it, the morning is soon enough.
INTERRUPT_ABOVE = 55

#: How often a night runs where nobody has said otherwise. Daily, because that is what both
#: deployment shapes ship with — a 02:00 cron at the edge, a sleep loop under compose.
DEFAULT_CADENCE_HOURS = 24

#: Silence is measured against the cadence, not against a constant: a programme that works its
#: engagement weekly is not failing on a Tuesday. Half a cycle of slack, so a late run is not an
#: alarm and a missed one cannot hide behind the next.
SILENCE_FACTOR = 1.5

#: Where a cadence other than the default is declared. A projection input like everything else —
#: the declaration is a ledger entry, so the clock reads it from the same chain it reads the runs
#: from and no second store has to agree with the first.
CADENCE_ACTION = "NIGHT_CADENCE"

#: What the night leaves behind on every run. The one durable record that a night happened.
HANDOVER_ACTION = "HANDOVER"

#: A night that started and did not finish. Written by the kernel when the run raises, so a
#: failure is a fact on the chain rather than an exit code one deployment shape happens to read.
FAILED_ACTION = "NIGHT_FAILED"


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
        people: list[Person] | None = None, now: datetime | None = None,
        load: dict | None = None, latency: dict | None = None) -> dict:
    """Rank the night's findings, spend the interruption budget, leave the rest for the morning.

    The budget is spent on cost, not on order of discovery — a chain break found at 04:00 outranks
    a stale attestation found at 22:00, and a night that finds four urgent things still only
    interrupts three times and says so in the handover rather than quietly dropping the fourth.

    `load` is what each person has already been asked this week, and the night spends it as it
    routes: the costliest findings take capacity first, so a night that fills somebody up does it
    on the things that mattered most.
    """
    scheduler = Scheduler(interruption_budget=budget)
    for f in sorted(night.findings, key=lambda f: -f.cost):
        scheduler.submit(f.what, cost_of_silence=f.cost, shift=Shift.NIGHT,
                         interrupts_human=f.cost >= interrupt_above)
    ran = scheduler.run(Shift.NIGHT)
    interrupted = [t.name for t in ran if t.interrupts_human]
    by_name = {f.what: f for f in night.findings}

    running = dict(load or {})

    def rows(names):
        return [_routed(by_name[n], people, now, interrupt_above, running, latency)
                for n in names if n in by_name]

    # Order matters: capacity is spent on the costliest findings first, so what is left unasked
    # when somebody fills up is the thing that mattered least.
    urgent, held = rows(interrupted), rows(scheduler.handover()["deferred"])
    return {"did": list(night.did),
            "interrupted": urgent,
            "deferred": held,
            "waited": rows([t.name for t in ran if not t.interrupts_human]),
            "budget": {"of": budget, "spent": len(interrupted),
                       "held_back": len(scheduler.handover()["deferred"]),
                       "threshold": interrupt_above},
            "cost_of_silence": dict(COST_OF_SILENCE)}


def cadence(entries: list[dict]) -> int:
    """How often this engagement has said its nights run, in hours. The last declaration wins."""
    declared = [e for e in entries if e.get("action") == CADENCE_ACTION]
    if not declared:
        return DEFAULT_CADENCE_HOURS
    try:
        return max(1, int(declared[-1].get("hours", DEFAULT_CADENCE_HOURS)))
    except (TypeError, ValueError):
        return DEFAULT_CADENCE_HOURS


def clock(entries: list[dict], now: datetime | None = None) -> dict:
    """When a night last ran, whether it finished, and whether one is overdue — all off the ledger.

    A night shift nobody knows stopped happening is worse than one that never started, and every
    way it stops — a rotated token, a cron that is not firing, an edge that was never deployed, a
    kernel the edge cannot reach — is invisible from inside the night that did not run. Nothing
    inside the night can report its own absence, so the chain reports it instead: a handover is
    written on every run, a failure is written when one raises, and the absence of both is the
    signal.

    Restart-proof for the same reason. The last handover is held in memory for the console to
    render; whether a night *happened* is a fact about the ledger.
    """
    now = now or datetime.now(timezone.utc)
    every = cadence(entries)
    overdue_after = every * SILENCE_FACTOR
    worked = [e.get("ts", "") for e in entries if e.get("action") == HANDOVER_ACTION]
    broke = [e for e in entries if e.get("action") == FAILED_ACTION]
    # A failure after the last success is the one still standing; a failure before it was fixed by
    # the night that followed, and reporting it would be a platform nursing a grudge.
    failed = broke[-1] if broke and (not worked or broke[-1].get("ts", "") > max(worked)) else None

    base = {"every_hours": every, "overdue_after_hours": round(overdue_after, 1),
            "failed_at": failed.get("ts", "") if failed else "",
            "failed_with": failed.get("detail", "") if failed else ""}

    if not worked:
        says = ("No night has ever been worked here. Either nobody has run one yet, or the clock "
                "that runs them is not deployed.")
        if failed:
            says = (f"No night has ever finished here. The last one started and raised "
                    f"{failed.get('detail', 'an error')} — that is a fault in the run, not a "
                    f"clock that is not firing.")
        return {**base, "last_worked": "", "silent_for_hours": None, "running": False,
                "says": says}

    last = max(worked)
    try:
        hours = (now - datetime.strptime(last, TS).replace(tzinfo=timezone.utc)).total_seconds() / 3600
    except ValueError:
        return {**base, "last_worked": last, "silent_for_hours": None, "running": True,
                "says": f"A night was worked at {last}."}
    hours = round(max(hours, 0.0), 1)

    if failed:
        return {**base, "last_worked": last, "silent_for_hours": hours, "running": False,
                "says": f"The last night raised {failed.get('detail', 'an error')} and did not "
                        f"finish. One completed {hours:g}h ago, and what it found may be stale."}
    if hours <= overdue_after:
        return {**base, "last_worked": last, "silent_for_hours": hours, "running": True,
                "says": f"The last night was worked {hours:g}h ago, and nights run every "
                        f"{every}h here."}
    # Days past a couple of them: "no night in 496h" is a number, "in 21 days" is a fact.
    span = f"{hours:g}h" if hours < 48 else f"{hours / 24:.0f} days"
    return {**base, "last_worked": last, "silent_for_hours": hours, "running": False,
            "says": f"No night has been worked in {span}, and one runs every {every}h here. The "
                    f"clock is not firing, the token it calls with was rotated, or the edge is "
                    f"not deployed — nothing here can tell which, and all three are silent."}


def _finding_dict(f: Finding) -> dict:
    return {"kind": f.kind, "what": f.what, "who": f.who, "detail": f.detail, "cost": f.cost,
            "needs": f.needs, "when": "", "why": ""}


def _routed(f: Finding, people, now, interrupt_above: int, running: dict, latency) -> dict:
    """Put a name to it where one is registered, and keep the role where none is.

    Routing never invents a person. With no team registered the handover says what it always
    said — a role — and says it without pretending that is the same thing as asking somebody.
    """
    out = _finding_dict(f)
    if not people or not f.needs:
        return out
    r = route(Ask(f.what, f.needs, f.cost, f.detail), people, now, interrupt_above, running,
              latency)
    if r.person is None:
        return {**out, "why": r.why}
    running[r.person.name] = running.get(r.person.name, 0) + 1
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
    # A finding routing could not place: it was put to somebody and came back — nobody holds the
    # authority, or everybody who does is at the week's capacity. It keeps its role for context
    # and is listed as unasked, because a bottleneck printed as an ask is a bottleneck hidden.
    unplaced = [f for f in found if f.get("why") and not f.get("when")]
    asks = [f for f in found if f["who"] and f not in unplaced]
    if not asks:
        lines.append("- Nothing from me. I will keep checking.")
    else:
        for f in asks:
            when = f.get("when")
            lines.append(f"- {f['who']}{' — ' + when if when and when != 'now' else ''}: "
                         f"{f['what']}")
    for f in unplaced:
        # Say it plainly rather than dropping it: an ask with no owner is the finding.
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
