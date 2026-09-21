"""People the platform may ask for something, and the rules for choosing which one.

M4 of the team-member model: team membership means knowing who does what and asking the right
person directly. Until now the handover named a role — "whoever makes the change" — which is
honest and useless: a request addressed to nobody is a request nobody answers.

Three rules, and they are the whole module:

  **Cheapest sufficient authority.** Not the most senior person who could sign it — the least
  senior who can. Seniority is a scarce resource on a programme and spending it on a decision a
  team lead could make is how approval queues form. `cost` is what the organisation says an hour
  of that person's attention is worth to the programme; it is set, not inferred, because a
  platform that guessed at somebody's seniority would be guessing about a person.

  **The clock is theirs, not ours.** Nothing pings Maputo at 06:00 on a Saturday. Working hours
  are per person, in their own timezone offset, and a request outside them waits — unless what is
  waiting costs more than the interruption does, which is the one case the night shift already
  knows how to price (ADR-0027).

  **Authority is what they can sign, not what they are called.** A person holds capabilities —
  the platform's own permission names — so routing asks "who may resolve a statutory decision"
  rather than "who is senior enough", and the answer is checked against the same table the API
  gates on.

Pure stdlib, pure over its inputs: people and a moment go in, a name comes out. Nothing here
sends anything, and nothing here knows what a notification is.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class Person:
    """Someone the platform may address. Everything here is declared by the organisation."""
    name: str
    #: Permission names, as `auth.ROLE_PERMISSIONS` spells them: approve, resolve_dp, execute…
    authority: frozenset = frozenset()
    #: What an hour of this person's attention costs the programme. Higher is scarcer. Set, never
    #: inferred — a platform that guessed somebody's seniority would be guessing about a person.
    cost: int = 1
    #: Local working hours, inclusive start and exclusive end, in their own offset.
    hours: tuple = (9, 17)
    #: Hours east of UTC. An integer because the platform schedules days, not launches.
    utc_offset: int = 0
    #: Days they work, Monday = 0, as `datetime.weekday()` numbers them.
    days: frozenset = frozenset({0, 1, 2, 3, 4})
    #: Approvals per week this person can absorb. Capacity is a real constraint at scale and the
    #: reason a queue forms behind one name.
    capacity_per_week: int = 20

    def local(self, when: datetime) -> datetime:
        return when.astimezone(timezone(timedelta(hours=self.utc_offset)))

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


def route(ask: Ask, people: list[Person], now: datetime | None = None,
          interrupt_above: int = 55) -> Routing:
    """The cheapest sufficient authority, and when they will actually see it.

    Availability does not change *who* is asked — swapping to a more expensive person because the
    right one is asleep is how a programme teaches itself to wake partners. It changes *when*,
    and a request above the interruption threshold goes now regardless, because at that price the
    person would rather be woken.
    """
    now = now or datetime.now(timezone.utc)
    able = sorted((p for p in people if ask.needs in p.authority), key=lambda p: (p.cost, p.name))
    if not able:
        return Routing(ask, None, "",
                       f"nobody registered on this engagement may '{ask.needs}'. Someone who can "
                       f"has to be added before this can be asked of anyone.")

    person = able[0]
    cheaper_than = [p.name for p in able[1:]]
    why = f"the least senior person registered who may '{ask.needs}'"
    if cheaper_than:
        why += f", ahead of {', '.join(cheaper_than)}"

    if person.available(now):
        return Routing(ask, person, "now", why)
    if ask.cost_of_silence >= interrupt_above:
        return Routing(ask, person, "now",
                       f"{why}. Outside their hours, and it is worth it at this cost.")
    when = person.next_available(now)
    return Routing(ask, person, f"at {when:%a %H:%M} their time",
                   f"{why}. Outside their working hours, and this can wait.")


def route_all(asks: list[Ask], people: list[Person], now: datetime | None = None,
              interrupt_above: int = 55) -> list[Routing]:
    return [route(a, people, now, interrupt_above) for a in asks]


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
            utc_offset=int(row.get("utc_offset", 0)),
            days=frozenset(row.get("days") if row.get("days") is not None else {0, 1, 2, 3, 4}),
            capacity_per_week=int(row.get("capacity_per_week", 20))))
    return out
