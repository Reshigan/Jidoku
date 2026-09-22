"""The delta pool: a budget that can be exhausted, not a number in a slide."""
from jidoka_core.delta import DEFAULT_POOL, size, spent, state
from jidoka_core.ir import validate_record

SIGNED = {"workbook": "w.xlsx", "signed_by": "T. Mabaso", "date": "2026-09-01"}


def rec(code, owner=None):
    raw = {"object": "CustomThing", "product": "SuccessFactors", "system_binding": "SYS",
           "external_code": code, "tier": "A", "source": dict(SIGNED),
           "intent": {"externalCode": code}}
    if owner:
        raw["contract"] = {"owner": owner}
    return validate_record(raw)[0]


def test_a_customisation_is_an_object_with_a_contract():
    """Delivered standard configuration has no owner to declare, so counting it would make the
    pool a count of the design rather than of what the programme built."""
    records = [rec("std1"), rec("std2"), rec("custom1", owner="EC")]
    assert spent(records) == ["SuccessFactors:CustomThing:custom1"]


def test_the_default_is_thirty_and_it_is_a_commercial_fact_not_a_law():
    assert size([]) == DEFAULT_POOL
    assert size([{"action": "DELTA_POOL", "size": 5}]) == 5


def test_the_last_declaration_wins_because_a_pool_is_renegotiated():
    assert size([{"action": "DELTA_POOL", "size": 5}, {"action": "DELTA_POOL", "size": 45}]) == 45


def test_a_pool_with_room_says_how_much():
    out = state([rec(str(i), owner="EC") for i in range(29)], [])
    assert out["remaining"] == 1 and out["over"] == 0
    assert "1 left" in out["says"]


def test_an_empty_pool_names_the_next_one_as_a_conversation_not_a_build():
    out = state([rec(str(i), owner="EC") for i in range(30)], [])
    assert out["remaining"] == 0 and out["over"] == 0
    assert "commercial conversation, not a build" in out["says"]


def test_going_over_says_who_agreed_to_the_number():
    out = state([rec(str(i), owner="EC") for i in range(32)], [])
    assert out["over"] == 2 and "somebody agreed to 30" in out["says"]


def test_it_is_counted_from_the_design_not_from_what_was_built():
    """The commercial question is asked when somebody proposes the thirty-first — not after it has
    reached a tenant, which is too late for it to be a question."""
    records = [rec(str(i), owner="EC") for i in range(31)]
    assert state(records, [])["over"] == 1, "nothing has been executed and the pool is already over"
    assert "asked when somebody proposes the thirty-first" in state(records, [])["method"]
