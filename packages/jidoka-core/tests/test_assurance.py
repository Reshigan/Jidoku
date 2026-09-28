"""Assurance: what the platform can prove, counted from its own chain.

The number is quotable only if it cannot be nudged. Each test here names something that must not
move it, or something that must.
"""
import pytest
from jidoka_core.assurance import CLAIMED, assure, verdicts
from jidoka_core.ir import IRRecord, record_key


def rec(code, tier="A"):
    return IRRecord(object="TimeType", product="SuccessFactors", system_binding="SF-DEV",
                    intent={"externalCode": code}, tier=tier, external_code=code,
                    source={"workbook": "w.xlsx", "signed_by": "lead", "date": "2026-01-01"})


def chain(pairs):
    return [{"task": record_key(rec(code)), "action": action} for code, action in pairs]


def test_a_person_s_word_is_never_counted_as_proof():
    """The whole reason this exists: the sum of the two is the number somebody would quote."""
    a = assure([rec("A"), rec("B")], chain([("A", "VERIFIED"), ("B", "ATTESTED")])).as_dict()
    assert a["counts"] == {"checked": 1, "attested": 1}
    assert a["proven"] == 1 and a["claimed"] == 2 and a["fraction"] == 0.5


def test_unbuilt_and_outstanding_work_cannot_move_the_number():
    """Nobody claims they are done, so counting them would move the score for reasons that have
    nothing to do with evidence — in either direction, depending which way you folded them."""
    base = assure([rec("A")], chain([("A", "VERIFIED")])).as_dict()
    with_more = assure([rec("A"), rec("B"), rec("C")],
                       chain([("A", "VERIFIED"), ("B", "NOT_APPLIED"),
                              ("C", "AWAITING_A_PERSON")])).as_dict()
    assert base["fraction"] == with_more["fraction"] == 1.0
    assert with_more["claimed"] == base["claimed"] == 1
    assert with_more["records"] == 3


def test_a_record_nothing_has_looked_at_is_unexamined_not_assumed():
    a = assure([rec("A")], []).as_dict()
    assert a["counts"] == {"unexamined": 1}
    assert a["fraction"] is None, "an empty set has no fraction, and 0.0 reads as a failure"


def test_the_latest_verdict_wins():
    """Unreadable yesterday, attested today."""
    a = assure([rec("A")], chain([("A", "UNCONFIRMABLE"), ("A", "ATTESTED")])).as_dict()
    assert a["counts"] == {"attested": 1}


def test_a_drifted_record_is_claimed_and_never_proven():
    a = assure([rec("A")], chain([("A", "DRIFT_DETECTED")])).as_dict()
    assert a["claimed"] == 1 and a["proven"] == 0 and a["fraction"] == 0.0


def test_an_unevidenced_record_drags_the_number_down_rather_than_hiding():
    """No read path and nobody's word: the honest treatment is to count it against the total."""
    a = assure([rec("A"), rec("B")], chain([("A", "VERIFIED"), ("B", "UNCONFIRMABLE")])).as_dict()
    assert a["fraction"] == 0.5


def test_the_formula_and_its_blind_spots_travel_with_the_number():
    a = assure([rec("A")], chain([("A", "VERIFIED")])).as_dict()
    assert "checked / (checked + disagrees + attested + unevidenced)" in a["formula"]
    assert len(a["not_counted"]) == 3


def test_it_counts_a_record_the_same_whether_it_arrives_as_a_row_or_a_dataclass():
    """The API holds dataclasses and the projections hold rows. A count that saw only one of them
    reported every record as unexamined."""
    as_row = {"object": "TimeType", "product": "SuccessFactors", "system_binding": "SF-DEV",
              "intent": {"externalCode": "A"}, "tier": "A", "external_code": "A"}
    entries = chain([("A", "VERIFIED")])
    assert assure([rec("A")], entries).as_dict()["counts"] == \
        assure([as_row], entries).as_dict()["counts"] == {"checked": 1}


def test_every_claimed_basis_is_one_the_ledger_actually_writes():
    """A basis nothing writes would be a column that is always zero and always reassuring."""
    from jidoka_core.assurance import BASIS

    assert set(CLAIMED) <= set(BASIS.values())


def test_verdicts_ignores_ledger_actions_that_are_not_verdicts():
    assert verdicts([{"task": "t", "action": "SNAPSHOT"}, {"task": "t", "action": "EXECUTED"}]) == {}
