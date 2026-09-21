"""Routing: the cheapest sufficient authority, on their clock, never invented."""
from datetime import datetime, timezone

from jidoka_os.people import Ask, Person, load, route, route_all

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
