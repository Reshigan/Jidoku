"""A collision refused at allocation is a defect that never reaches integration testing."""
import pytest
from jidoka_core.ledger import Ledger
from jidoka_core.numbering import NumberRange, NumberRanges, NumberingError


def _nr():
    return NumberRanges(Ledger())


def _rng(**over):
    base = dict(range_id="TT-ZA", object_type="TimeType", prefix="TT_ZA_", start=1, end=3, width=3)
    base.update(over)
    return NumberRange(**base)


def test_allocation_hands_out_sequential_codes_and_ledgers_each():
    nr = _nr()
    nr.register(_rng(), "lead")
    assert nr.allocate("TimeType", "amara") == "TT_ZA_001"
    assert nr.allocate("TimeType", "sipho") == "TT_ZA_002"
    assert [e["action"] for e in nr.ledger.entries] == ["RANGE_REGISTERED", "CODE_ALLOCATED",
                                                        "CODE_ALLOCATED"]


def test_a_requested_code_collision_is_refused_and_names_the_holder():
    nr = _nr()
    nr.register(_rng(), "lead")
    nr.allocate("TimeType", "amara", code="TT_ZA_002")
    with pytest.raises(NumberingError) as ex:
        nr.allocate("TimeType", "sipho", code="TT_ZA_002")
    assert "amara" in str(ex.value)


def test_a_code_outside_every_range_is_refused():
    nr = _nr()
    nr.register(_rng(), "lead")
    with pytest.raises(NumberingError):
        nr.allocate("TimeType", "sipho", code="TT_ZA_999")


def test_exhaustion_is_refused_not_wrapped():
    nr = _nr()
    nr.register(_rng(end=1), "lead")
    nr.allocate("TimeType", "amara")
    with pytest.raises(NumberingError) as ex:
        nr.allocate("TimeType", "sipho")
    assert "exhausted" in str(ex.value)


def test_overlapping_ranges_for_one_object_type_are_refused():
    nr = _nr()
    nr.register(_rng(), "lead")
    with pytest.raises(NumberingError):
        nr.register(_rng(range_id="TT-ZA-2", start=3, end=9), "lead")


def test_codes_are_never_released():
    nr = _nr()
    nr.register(_rng(), "lead")
    nr.allocate("TimeType", "amara")
    assert not any(hasattr(nr, m) for m in ("release", "free", "deallocate"))


def test_validate_constrains_only_governed_object_types():
    nr = _nr()
    nr.register(_rng(), "lead")
    assert nr.validate("TimeType", "TT_ZA_002") is None
    assert "outside every registered" in nr.validate("TimeType", "PAYCOMP_9")
    assert nr.validate("PayComponent", "anything-at-all") is None  # ungoverned = unconstrained


def test_snapshot_shows_next_free_per_range():
    nr = _nr()
    nr.register(_rng(), "lead")
    nr.allocate("TimeType", "amara")
    snap = nr.snapshot()
    assert snap["ranges"][0]["next_free"] == "TT_ZA_002"
    assert snap["allocated"] == {"TT_ZA_001": "amara"}
