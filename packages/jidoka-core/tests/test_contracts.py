"""One writer, declared readers — the rule that keeps modules from colliding."""
import pytest

from jidoka_core.contracts import (ContractError, conflicts, consumers_of, registry,
                                   undeclared_readers, validate)
from jidoka_core.ir import IRValidationError, validate_record
from jidoka_core.planner import PlanError, plan

SIGNED = {"workbook": "ZA-payroll-v3.xlsx", "signed_by": "T. Mabaso", "date": "2026-09-01"}


def rec(object_, code, owner=None, consumers=(), depends=(), product="SuccessFactors"):
    raw = {"object": object_, "product": product, "system_binding": "KOM-SF-DEV",
           "intent": {"externalCode": code}, "tier": "A", "source": dict(SIGNED),
           "external_code": code, "depends_on": list(depends)}
    if owner:
        raw["contract"] = {"owner": owner, "consumers": list(consumers)}
    return raw


def loaded(raws):
    return [validate_record(r)[0] for r in raws]


def test_a_contract_that_names_no_owner_is_a_field_with_paperwork():
    with pytest.raises(IRValidationError, match="field with paperwork"):
        validate_record({**rec("PicklistOption", "MIBCO"), "contract": {"consumers": ["Time Off"]}})


def test_consumers_must_be_a_list_not_a_sentence():
    with pytest.raises(ContractError, match="list of module names"):
        validate({"object": "X", "product": "SF", "intent": {},
                  "contract": {"owner": "EC", "consumers": "Time Off and payroll"}})


def test_standard_configuration_needs_no_contract():
    """The contract exists for the objects a programme builds, which are exactly the objects that
    later surprise it. Refusing the delivered standard for lacking one would be paperwork."""
    records = loaded([rec("PicklistOption", "STANDARD")])
    assert registry(records) == {} and conflicts(records) == {}


def test_two_modules_claiming_to_write_the_same_object_block_the_plan():
    """A design decision nobody has made, not a merge to resolve by whoever saves last."""
    records = loaded([rec("CustomString", "custom-string4", owner="EC"),
                      rec("CustomString", "custom-string4", owner="Time Off")])
    assert conflicts(records)
    with pytest.raises(PlanError, match="two modules claim to write the same object"):
        plan(records, {})


def test_one_writer_with_readers_plans_normally():
    records = loaded([rec("CustomString", "custom-string4", owner="EC",
                          consumers=["Time Off", "EE Reporting", "ECC Payroll"])])
    assert plan(records, {})["steps"]
    assert consumers_of(records, records[0].key) == ["ECC Payroll", "EE Reporting", "Time Off"]


def test_a_module_reading_an_object_it_is_not_registered_against_is_named():
    """The owner will change the object one day without knowing who breaks."""
    owner = rec("CustomString", "custom-string4", owner="EC", consumers=["EE Reporting"])
    reader = rec("TimeAccountType", "ANN_ACC_ZAF", owner="Time Off",
                 depends=["CustomString:custom-string4"])
    out = undeclared_readers(loaded([owner, reader]))
    assert len(out) == 1
    assert out[0]["module"] == "Time Off" and out[0]["owner"] == "EC"
    assert "will not know who breaks" in out[0]["says"]


def test_a_registered_reader_is_not_a_finding():
    owner = rec("CustomString", "custom-string4", owner="EC", consumers=["Time Off"])
    reader = rec("TimeAccountType", "ANN_ACC_ZAF", owner="Time Off",
                 depends=["CustomString:custom-string4"])
    assert undeclared_readers(loaded([owner, reader])) == []


def test_the_owner_reading_its_own_object_is_not_a_finding():
    owner = rec("CustomString", "custom-string4", owner="EC", consumers=[])
    other = rec("TimeAccountType", "ANN_ACC_ZAF", owner="EC",
                depends=["CustomString:custom-string4"])
    assert undeclared_readers(loaded([owner, other])) == []


def test_an_undeclared_reader_is_a_finding_and_not_a_block():
    """A dependency is a fact about the design; this is the paperwork having fallen behind it."""
    owner = rec("CustomString", "custom-string4", owner="EC")
    reader = rec("TimeAccountType", "ANN_ACC_ZAF", owner="Time Off",
                 depends=["CustomString:custom-string4"])
    records = loaded([owner, reader])
    assert undeclared_readers(records) and plan(records, {})["steps"]


def test_short_references_resolve_the_way_the_planner_resolves_them():
    """Two resolvers would disagree the first time one of them learned a new form."""
    owner = rec("CustomString", "custom-string4", owner="EC")
    by_short = rec("A", "a1", owner="Time Off", depends=["CustomString:custom-string4"])
    records = loaded([owner, by_short])
    assert [f["reads"] for f in undeclared_readers(records)] == [records[0].key]
