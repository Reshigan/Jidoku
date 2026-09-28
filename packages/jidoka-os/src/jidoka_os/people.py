"""People the platform may ask for something, and the rules for choosing which one.

M4 of the team-member model: team membership means knowing who does what and asking the right
person directly. Until now the handover named a role — "whoever makes the change" — which is
honest and useless: a request addressed to nobody is a request nobody answers.

Four rules, and they are the whole module:

  **Cheapest sufficient authority.** Not the most senior person who could sign it — the least
  senior who can. Seniority is a scarce resource on a programme and spending it on a decision a
  team lead could make is how approval queues form. `cost` is what the organisation says an hour
  of that person's attention is worth to the programme; it is set, not inferred, because a
  platform that guessed at somebody's seniority would be guessing about a person.

  **The clock is theirs, not ours.** Nothing pings Maputo at 06:00 on a Saturday. Working hours
  are per person, in their own named timezone — so they move with daylight saving rather than
  being right eleven months of the year — and a request outside them waits, unless what is waiting
  costs more than the interruption does, which is the one case the night shift already knows how
  to price (ADR-0027).

  **Capacity is a real constraint and the queue behind one name is the finding.** What each person
  has already been asked this week is read off the ledger, and somebody at their declared capacity
  is passed over for the next cheapest sufficient authority. When everybody who could answer is
  full, that is said out loud rather than quietly making it somebody's problem tomorrow.

  **Authority is what they can sign, not what they are called.** A person holds capabilities —
  the platform's own permission names — so routing asks "who may resolve a statutory decision"
  rather than "who is senior enough", and the answer is checked against the same table the API
  gates on.

Pure stdlib, pure over its inputs: people and a moment go in, a name comes out. Nothing here
sends anything, and nothing here knows what a notification is.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from jidoka_core.clock import TS
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

#: The ledger action that records the platform having asked somebody for something. One entry per
#: person per thing per week: asking the same person the same question on five consecutive nights
#: is one ask against their capacity, because it is one thing they owe.
ASKED = "ASKED"


def zone(name: str):
    """The named zone if the tz database knows it, else None.

    A named zone moves with daylight saving; a fixed offset does not. The offset stays as the
    fallback because a slim container may ship without a tz database, and being an hour out in
    March beats refusing to route at all — but an unknown name is a 422 at registration, so this
    only ever falls back for a zone that was valid when it was declared.
    """
    try:
        return ZoneInfo(name) if name else None
    except (ZoneInfoNotFoundError, ValueError):
        return None


def week_start(now: datetime | None = None) -> str:
    """Monday 00:00 UTC, as the ledger writes a timestamp. Capacity is a week's worth and a week
    starts somewhere; it starts here, for everybody, so two people's capacity means the same."""
    now = now or datetime.now(timezone.utc)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0,
                                                           microsecond=0)
    return monday.strftime(TS)


@dataclass(frozen=True)
class Person:
    """Someone the platform may address. Everything here is declared by the organisation."""
    name: str
    #: Permission names, as `auth.ROLE_PERMISSIONS` spells them: approve, resolve_dp, execute…
    authority: frozenset = frozenset()
    #: What an hour of this person's attention costs the programme. Higher is scarcer. Set, never
    #: inferred — a platform that guessed somebody's seniority would be guessing about a person.
    cost: int = 1
    #: Local working hours, inclusive start and exclusive end, in their own zone.
    hours: tuple = (9, 17)
    #: IANA zone name — "Africa/Maputo". Named, so the hours move with daylight saving.
    tz: str = ""
    #: Hours east of UTC. The fallback when no zone is named, and what a zone the running image
    #: has no database for degrades to.
    utc_offset: int = 0
    #: Days they work, Monday = 0, as `datetime.weekday()` numbers them.
    days: frozenset = frozenset({0, 1, 2, 3, 4})
    #: Approvals per week this person can absorb. Capacity is a real constraint at scale and the
    #: reason a queue forms behind one name.
    capacity_per_week: int = 20

    def local(self, when: datetime) -> datetime:
        return when.astimezone(zone(self.tz) or timezone(timedelta(hours=self.utc_offset)))

    def available(self, when: datetime) -> bool:
        here = self.local(when)
        return here.weekday() in self.days and self.hours[0] <= here.hour < self.hours[1]

    def next_available(self, when: datetime) -> datetime:
        """The next moment inside their working week. Bounded: a person who works no days at all
        is a declaration error, and returning `when` is better than looping forever over it."""
        here = self.local(when)
        for _ in range(14 * 24):
            if here.weekday() in self.days and self.hours[0] <= here.hour < self.hours[1]:
                return here
            here += timedelta(hours=1)
            here = here.replace(minute=0, second=0, microsecond=0)
        return self.local(when)


@dataclass
class Ask:
    """One thing that needs a person. `needs` is the permission it takes to answer it."""
    what: str
    needs: str
    cost_of_silence: int = 0
    detail: str = ""


@dataclass(frozen=True)
class Routing:
    ask: Ask
    person: Person | None
    when: str            # "now", "at <local time>", or "" when nobody can answer it
    why: str

    def as_dict(self) -> dict:
        return {"what": self.ask.what, "needs": self.ask.needs,
                "who": self.person.name if self.person else "",
                "when": self.when, "why": self.why,
                "cost_of_silence": self.ask.cost_of_silence, "detail": self.ask.detail}


def asked_this_week(entries: list[dict], now: datetime | None = None) -> dict[str, int]:
    """How much of their week each person has already been asked for, read off the ledger.

    Distinct things, not entries: the same question put to the same person on five consecutive
    nights is one thing they owe, and counting it five times would retire somebody on repeats.
    """
    since = week_start(now)
    seen = {(e.get("person"), e.get("detail")) for e in entries
            if e.get("action") == ASKED and e.get("ts", "") >= since and e.get("person")}
    out: dict[str, int] = {}
    for who, _ in seen:
        out[who] = out.get(who, 0) + 1
    return out


def observed_latency(entries: list[dict]) -> dict[str, float]:
    """Median hours each person has taken to answer a decision on this engagement.

    Reported, never ranked on. Routing around somebody because they are slow is an organisational
    decision the platform has no standing to make — it would quietly reassign work on the strength
    of a median, and the person it routed around would never know. So it goes in the reason the
    handover gives, where the human reading it can do something about it.
    """
    raised: dict[str, str] = {}
    waits: dict[str, list[float]] = {}
    for e in entries:
        task = e.get("task")
        if e.get("action") == "DP_RAISED":
            raised[task] = e.get("ts", "")
        elif e.get("action") == "DP_RESOLVED" and task in raised:
            try:
                t0 = datetime.strptime(raised.pop(task), TS)
                t1 = datetime.strptime(e.get("ts", ""), TS)
            except ValueError:
                continue
            if t1 >= t0 and e.get("actor"):
                waits.setdefault(e["actor"], []).append((t1 - t0).total_seconds() / 3600)
    return {who: round(median(hrs), 1) for who, hrs in waits.items()}


def route(ask: Ask, people: list[Person], now: datetime | None = None,
          interrupt_above: int = 55, load: dict[str, int] | None = None,
          latency: dict[str, float] | None = None) -> Routing:
    """The cheapest sufficient authority with room left this week, and when they will see it.

    Availability does not change *who* is asked — swapping to a more expensive person because the
    right one is asleep is how a programme teaches itself to wake partners. It changes *when*,
    and a request above the interruption threshold goes now regardless, because at that price the
    person would rather be woken.

    Capacity does change who. Somebody at the limit their organisation declared is passed over for
    the next cheapest person who can sign it, and when everybody who can is full, nobody is asked
    and the queue is the finding.
    """
    now = now or datetime.now(timezone.utc)
    load, latency = load or {}, latency or {}
    able = sorted((p for p in people if ask.needs in p.authority), key=lambda p: (p.cost, p.name))
    if not able:
        return Routing(ask, None, "",
                       f"nobody registered on this engagement may '{ask.needs}'. Someone who can "
                       f"has to be added before this can be asked of anyone.")

    free = [p for p in able if load.get(p.name, 0) < p.capacity_per_week]
    if not free:
        queue = ", ".join(f"{p.name} {load.get(p.name, 0)}/{p.capacity_per_week}" for p in able)
        return Routing(ask, None, "",
                       f"everybody who may '{ask.needs}' is at the week's capacity their "
                       f"organisation declared ({queue}). The queue behind those names is the "
                       f"finding, and one more ask into it would only hide it.")

    person = free[0]
    full = [p.name for p in able[:able.index(person)]]
    why = f"the least senior person registered who may '{ask.needs}'"
    if full:
        why += f", past {', '.join(full)} at the week's capacity"
    if free[1:]:
        why += f", ahead of {', '.join(p.name for p in free[1:])}"
    if person.name in latency:
        why += f". They have answered in {latency[person.name]:g}h on this engagement"

    if person.available(now):
        return Routing(ask, person, "now", why)
    if ask.cost_of_silence >= interrupt_above:
        return Routing(ask, person, "now",
                       f"{why}. Outside their hours, and it is worth it at this cost.")
    when = person.next_available(now)
    return Routing(ask, person, f"at {when:%a %H:%M} their time",
                   f"{why}. Outside their working hours, and this can wait.")


def route_all(asks: list[Ask], people: list[Person], now: datetime | None = None,
              interrupt_above: int = 55, load: dict[str, int] | None = None,
              latency: dict[str, float] | None = None) -> list[Routing]:
    """Asks in the order given, each one spending the capacity the one before it took. A batch
    that ignored its own effect on the week would hand one person everything it found."""
    running = dict(load or {})
    out = []
    for ask in asks:
        r = route(ask, people, now, interrupt_above, running, latency)
        if r.person:
            running[r.person.name] = running.get(r.person.name, 0) + 1
        out.append(r)
    return out


def load(rows: list[dict]) -> list[Person]:
    """People as the organisation declared them. Unknown fields are ignored rather than fatal:
    a directory export carries more than this needs."""
    out = []
    for row in rows:
        out.append(Person(
            name=row["name"],
            authority=frozenset(row.get("authority") or ()),
            cost=int(row.get("cost", 1)),
            hours=tuple(row.get("hours") or (9, 17)),
            tz=str(row.get("tz") or ""),
            utc_offset=int(row.get("utc_offset", 0)),
            days=frozenset(row.get("days") if row.get("days") is not None else {0, 1, 2, 3, 4}),
            capacity_per_week=int(row.get("capacity_per_week", 20))))
    return out
