"""C1: the rule travels with the value, and the plan is type-checked.

Whole classes of defect become unrepresentable rather than detected — and the type-checker's
rejection is the auditor's control narrative, verbatim.
"""
import pytest

from jidoka_core.ir import IRValidationError, validate_record
from jidoka_core.planner import PlanError, plan
from jidoka_core.refinements import RefinementError, check, missing_required, validate

SIGNED = {"workbook": "ZA-payroll-v3.xlsx", "signed_by": "T. Mabaso", "date": "2026-09-01"}
CEILING = {"kind": "bounded", "max": 15, "statute": "BCEA s20", "signed_by": "T. Mabaso",
           "date": "2026-09-01"}


def rec(object_, code, intent=None, product="SuccessFactors"):
    return {"object": object_, "product": product, "system_binding": "KOM-SF-DEV",
            "external_code": code, "tier": "A", "source": dict(SIGNED),
            "intent": {"externalCode": code, **(intent or {})}}


def loaded(raws):
    return [validate_record(r)[0] for r in raws]


# --- a bound with no authority is an opinion ---------------------------------------------------

def test_a_statutory_ceiling_with_no_signed_authority_does_not_load():
    """Invariant 1 does not stop applying because the number is in a type rather than a field."""
    bad = {"kind": "bounded", "max": 15}
    with pytest.raises(IRValidationError, match="cites no authority"):
        validate_record(rec("TimeType", "ANN", {"entitlement": {"value": 10, "refinement": bad}}))


def test_a_bound_that_bounds_nothing_does_not_load():
    with pytest.raises(RefinementError, match="declares a max, a min, or both"):
        validate({"object": "T", "product": "SF", "intent": {
            "x": {"value": 1, "refinement": {"kind": "bounded", "statute": "s", "signed_by": "a",
                                             "date": "d"}}}})


def test_a_constraint_the_checker_cannot_read_is_a_comment():
    with pytest.raises(IRValidationError, match="looks like protection"):
        validate_record(rec("TimeType", "ANN",
                            {"x": {"value": 1, "refinement": {"kind": "vibes"}}}))


# --- bounded ------------------------------------------------------------------------------------

def test_a_value_above_a_statutory_maximum_is_not_a_configuration_choice():
    records = loaded([rec("TimeType", "ANN", {"entitlement": {"value": 21, "refinement": CEILING}})])
    fail = check(records)[0]
    assert "configured as 21" in fail["says"] and "signed statutory maximum is 15" in fail["says"]
    assert "BCEA s20, signed by T. Mabaso on 2026-09-01" in fail["says"]
    assert "is not a configuration choice" in fail["says"]
    with pytest.raises(PlanError, match="does not type-check"):
        plan(records, {})


def test_a_value_inside_the_bound_plans_normally():
    records = loaded([rec("TimeType", "ANN", {"entitlement": {"value": 15, "refinement": CEILING}})])
    assert check(records) == [] and plan(records, {})["steps"]


def test_a_floor_is_as_real_as_a_ceiling():
    floor = {**CEILING, "max": None, "min": 15}
    floor.pop("max")
    records = loaded([rec("TimeType", "ANN", {"entitlement": {"value": 10, "refinement": floor}})])
    assert "signed statutory minimum is 15" in check(records)[0]["says"]


def test_a_non_numeric_value_under_a_numeric_limit_is_the_finding_not_a_crash():
    records = loaded([rec("TimeType", "ANN", {"entitlement": {"value": "twenty-one",
                                                              "refinement": CEILING}})])
    assert "not a number" in check(records)[0]["says"]


def test_an_undecided_value_is_not_a_type_error():
    """A refinement over a value nobody has decided would report the absence of a decision as a
    type error, and the platform already has a gate that says that better."""
    records = loaded([rec("TimeType", "ANN", {"entitlement": {"value": "TBD",
                                                              "refinement": CEILING}})])
    assert check(records) == []


# --- dependent ------------------------------------------------------------------------------------

DEP = {"kind": "dependent", "on": "LegalEntity:KOM-ZA", "field": "currency"}


def test_writing_the_same_fact_in_two_places_is_how_they_come_to_disagree():
    records = loaded([rec("LegalEntity", "KOM-ZA", {"currency": {"value": "ZAR"}}),
                      rec("TimeType", "ANN", {"currency": {"value": "USD", "refinement": DEP}})])
    fail = check(records)[0]
    assert "'USD'" in fail["says"] and "'ZAR'" in fail["says"]
    assert "which decides it" in fail["says"]


def test_agreement_is_not_a_finding():
    records = loaded([rec("LegalEntity", "KOM-ZA", {"currency": {"value": "ZAR"}}),
                      rec("TimeType", "ANN", {"currency": {"value": "ZAR", "refinement": DEP}})])
    assert check(records) == []


def test_a_dependency_on_something_that_does_not_exist_says_it_was_not_checked():
    """Silence would read as a pass, and the one thing this must never do is look like protection
    it did not provide."""
    records = loaded([rec("TimeType", "ANN", {"currency": {"value": "ZAR", "refinement": DEP}})])
    assert "cannot be checked, and was not" in check(records)[0]["says"]


def test_a_dependency_on_a_field_nobody_set_names_who_has_to_decide():
    records = loaded([rec("LegalEntity", "KOM-ZA", {"currency": {"value": ""}}),
                      rec("TimeType", "ANN", {"currency": {"value": "ZAR", "refinement": DEP}})])
    assert "it is not this one" in check(records)[0]["says"]


def test_a_dependent_refinement_naming_no_field_does_not_load():
    with pytest.raises(IRValidationError, match="names the object it depends on"):
        validate_record(rec("TimeType", "ANN",
                            {"currency": {"value": "ZAR",
                                          "refinement": {"kind": "dependent", "on": "X:1"}}}))


# --- required (R-107) ---------------------------------------------------------------------------

R107 = {"kind": "required", "rule": "R-107 (cycle context)"}


def test_a_field_every_schema_accepts_and_the_type_requires():
    """Wrong in a way nobody sees until the first accrual run."""
    records = loaded([rec("TimeType", "ANN", {"cycle_context": {"value": "", "refinement": R107}})])
    out = missing_required(records)
    assert "R-107 (cycle context) requires it" in out[0]["says"]
    with pytest.raises(PlanError, match="does not type-check"):
        plan(records, {})


def test_a_present_cycle_context_satisfies_it():
    records = loaded([rec("TimeType", "ANN",
                          {"cycle_context": {"value": "CALENDAR_YEAR", "refinement": R107}})])
    assert missing_required(records) == [] and plan(records, {})["steps"]


def test_absence_and_disagreement_are_reported_apart():
    """An auditor reads the two differently, and a list that mixed them would be sorted by hand."""
    records = loaded([rec("TimeType", "ANN",
                          {"entitlement": {"value": 21, "refinement": CEILING},
                           "cycle_context": {"value": "", "refinement": R107}})])
    assert len(check(records)) == 1 and len(missing_required(records)) == 1
