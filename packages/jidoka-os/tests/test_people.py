"""Routing: the cheapest sufficient authority, on their clock, never invented."""
from datetime import datetime, timezone

from jidoka_os.people import (Ask, Person, asked_this_week, load, observed_latency, route,
                              route_all, zone)

WED = datetime(2026, 9, 16, 9, 0, tzinfo=timezone.utc)      # 11:00 in Maputo
SAT = datetime(2026, 9, 19, 5, 0, tzinfo=timezone.utc)      # 07:00 in Maputo, a Saturday

JUNIOR = Person("A. Silva", frozenset({"resolve_dp"}), cost=1, utc_offset=2, hours=(8, 16))
SENIOR = Person("T. Mabaso", frozenset({"resolve_dp", "approve"}), cost=4, utc_offset=2)
TEAM = [SENIOR, JUNIOR]


def test_the_least_senior_person_who_can_sign_it_is_asked():
    """Spending a partner on a decision a team lead could make is how approval queues form."""
    r = route(Ask("DP-X needs a value", "resolve_dp"), TEAM, WED)
    assert r.person.name == "A. Silva" and r.when == "now"
    assert "least senior person registered who may 'resolve_dp'" in r.why
    assert "ahead of T. Mabaso" in r.why


def test_something_only_the_senior_can_sign_goes_to_the_senior():
    assert route(Ask("C-EXE-01 is failing", "approve"), TEAM, WED).person.name == "T. Mabaso"


def test_nobody_registered_who_can_answer_it_is_said_plainly():
    r = route(Ask("the arming lapsed", "arm"), TEAM, WED)
    assert r.person is None and r.when == ""
    assert "nobody registered on this engagement may 'arm'" in r.why


def test_a_routine_ask_outside_their_hours_waits_for_them():
    """Nothing pings Maputo at 07:00 on a Saturday."""
    r = route(Ask("a data model change needs attesting", "resolve_dp", 15), TEAM, SAT)
    assert r.person.name == "A. Silva"
    assert r.when == "at Mon 08:00 their time"
    assert "can wait" in r.why


def test_an_expensive_silence_goes_now_even_on_a_saturday():
    r = route(Ask("the chain does not verify", "resolve_dp", 100), TEAM, SAT)
    assert r.when == "now" and "worth it at this cost" in r.why


def test_availability_changes_when_not_who():
    """Swapping to a more expensive person because the right one is asleep is how a programme
    teaches itself to wake partners."""
    assert route(Ask("DP-X", "resolve_dp", 15), TEAM, SAT).person.name == \
        route(Ask("DP-X", "resolve_dp", 15), TEAM, WED).person.name


def test_a_tie_on_cost_is_broken_by_name_not_by_luck():
    """Two people who cost the same must route the same way on every run."""
    a, b = Person("B. One", frozenset({"approve"})), Person("A. Two", frozenset({"approve"}))
    assert route(Ask("x", "approve"), [a, b], WED).person.name == "A. Two"
    assert route(Ask("x", "approve"), [b, a], WED).person.name == "A. Two"


def test_working_days_are_theirs_to_declare():
    weekender = Person("Weekend cover", frozenset({"execute"}), utc_offset=2,
                       days=frozenset({5, 6}))
    assert weekender.available(SAT) is False        # 07:00 is before their hours
    assert weekender.available(SAT.replace(hour=8)) is True
    assert weekender.available(WED) is False


def test_somebody_who_works_no_days_does_not_hang_the_night():
    """A declaration error, and the night still has to end."""
    nobody = Person("Misconfigured", frozenset({"approve"}), days=frozenset())
    assert nobody.next_available(WED) is not None


def test_people_load_from_rows_and_ignore_what_they_do_not_need():
    people = load([{"name": "A. Silva", "authority": ["resolve_dp"], "cost": 2,
                    "email": "a@example.com", "utc_offset": 2}])
    assert people[0].name == "A. Silva" and people[0].cost == 2
    assert "resolve_dp" in people[0].authority


def test_routing_many_asks_keeps_them_in_order():
    asks = [Ask("first", "approve"), Ask("second", "resolve_dp")]
    assert [r.ask.what for r in route_all(asks, TEAM, WED)] == ["first", "second"]


# --- capacity: the queue behind one name is the finding (ADR-0029) ------------------------------

def test_somebody_at_their_weeks_capacity_is_passed_over_for_the_next_cheapest():
    """Capacity is the one thing that does change *who* — a person at their declared limit is
    not asked again, and the ask goes up, not into a queue."""
    r = route(Ask("DP-X", "resolve_dp"), TEAM, WED, load={"A. Silva": 20})
    assert r.person.name == "T. Mabaso"
    assert "past A. Silva at the week's capacity" in r.why


def test_everybody_full_is_said_out_loud_rather_than_queued_behind_one_name():
    r = route(Ask("DP-X", "resolve_dp"), TEAM, WED,
              load={"A. Silva": 20, "T. Mabaso": 20})
    assert r.person is None
    assert "at the week's capacity" in r.why and "A. Silva 20/20" in r.why


def test_a_batch_spends_the_capacity_it_uses_as_it_goes():
    """A night that ignored its own effect on the week would hand one person everything."""
    solo = Person("Only. One", frozenset({"approve"}), capacity_per_week=2)
    out = route_all([Ask(f"thing {i}", "approve") for i in range(3)], [solo], WED)
    assert [r.person.name if r.person else None for r in out] == ["Only. One", "Only. One", None]


def test_capacity_is_counted_from_the_ledger_and_a_repeat_ask_is_one_thing_owed():
    """The same unanswered question found on five nights is one thing that person owes."""
    week = [{"ts": "2026-09-14T09:00:00Z", "action": "ASKED", "person": "A. Silva",
             "detail": "DP-X needs a value"} for _ in range(5)]
    week.append({"ts": "2026-09-16T09:00:00Z", "action": "ASKED", "person": "A. Silva",
                 "detail": "DP-Y needs a value"})
    assert asked_this_week(week, WED) == {"A. Silva": 2}


def test_last_weeks_asks_are_not_this_weeks_capacity():
    last = [{"ts": "2026-09-09T09:00:00Z", "action": "ASKED", "person": "A. Silva",
             "detail": "DP-old"}]
    assert asked_this_week(last, WED) == {}


# --- the clock moves with daylight saving -------------------------------------------------------

def test_a_named_zone_moves_with_daylight_saving_and_an_offset_does_not():
    """09:00 UTC is inside a London working day in July and outside it in January. A fixed +0
    offset says the same thing in both months, and is wrong in one of them."""
    named = Person("L. Ondon", frozenset({"approve"}), tz="Europe/London", hours=(9, 10))
    fixed = Person("O. Ffset", frozenset({"approve"}), utc_offset=0, hours=(9, 10))
    july = datetime(2026, 7, 15, 9, 30, tzinfo=timezone.utc)      # 10:30 BST — after hours
    january = datetime(2026, 1, 14, 9, 30, tzinfo=timezone.utc)   # 09:30 GMT — at work
    assert named.available(july) is False and named.available(january) is True
    assert fixed.available(july) is True and fixed.available(january) is True


def test_an_unknown_zone_falls_back_to_the_declared_offset_rather_than_refusing_to_route():
    """The API refuses an unknown name at registration. If one reaches here — a slim image with
    no tz database — being an hour out beats routing nothing."""
    assert zone("Mars/Olympus") is None
    stranded = Person("S. Tranded", frozenset({"approve"}), tz="Mars/Olympus", utc_offset=2)
    assert stranded.available(WED) is True       # 11:00 in Maputo


# --- latency: observed, reported, never ranked on -----------------------------------------------

def test_how_long_somebody_takes_to_answer_is_read_off_the_ledger():
    entries = [{"ts": "2026-09-14T09:00:00Z", "task": "DP-1", "action": "DP_RAISED"},
               {"ts": "2026-09-14T13:00:00Z", "task": "DP-1", "action": "DP_RESOLVED",
                "actor": "A. Silva"},
               {"ts": "2026-09-15T09:00:00Z", "task": "DP-2", "action": "DP_RAISED"},
               {"ts": "2026-09-15T11:00:00Z", "task": "DP-2", "action": "DP_RESOLVED",
                "actor": "A. Silva"}]
    assert observed_latency(entries) == {"A. Silva": 3.0}


def test_being_slow_never_routes_around_anybody():
    """Reassigning somebody's work on the strength of a median is an organisational decision the
    platform has no standing to make. It is said out loud instead."""
    slow = {"A. Silva": 72.0}
    r = route(Ask("DP-X", "resolve_dp"), TEAM, WED, latency=slow)
    assert r.person.name == "A. Silva"
    assert "answered in 72h on this engagement" in r.why
