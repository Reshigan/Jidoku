"""The specification against the configuration.

The question these tests protect is the one nobody can answer on a real engagement: which
requirements does this configuration actually satisfy? The dangerous answer is a high percentage
computed over requirements nothing was ever traced to, so most of what is pinned here is the
platform refusing to count something.
"""
import pytest
from jidoka_core.requirements import (CONFIGURED, NOT_CONFIGURED, NOT_TRACEABLE, Control,
                                      Requirement, RequirementError, Specification, account,
                                      coverage, uncontrolled)


def spec():
    return Specification(
        requirements=[
            Requirement("BRS-EC-001", "Single instance, four country layers", "baseline",
                        "All", "W1", "STD", "C01", ("LegalEntity",)),
            Requirement("BRS-EC-002", "Picklist option set", "one source", "ZA", "W2", "CFG",
                        "C01", ("PicklistOption",)),
            Requirement("BRS-TIM-001", "Leave accrual by country", "statute", "ZA", "W3", "GAP",
                        "C02", ()),
        ],
        controls=[Control("C01", "Every change is attributable", "GONXT", "per cycle",
                          "the change log")])


IR = [{"object": "LegalEntity", "external_code": "KSA-ZA"}]


def test_a_requirement_needs_an_identifier_and_a_statement():
    with pytest.raises(RequirementError):
        Requirement("", "do a thing")
    with pytest.raises(RequirementError):
        Requirement("BRS-001", "   ")


def test_a_control_names_an_owner_and_the_evidence_it_produces():
    # A control everybody owns is one nobody runs, and an auditor asks for the name first.
    with pytest.raises(RequirementError):
        Control("C01", "attributable", "", "per cycle", "the change log")
    with pytest.raises(RequirementError):
        Control("C01", "attributable", "GONXT", "per cycle", "")


def test_a_requirement_traced_to_nothing_is_never_counted_as_covered():
    rows = {r["req_id"]: r for r in coverage(spec(), IR)}
    assert rows["BRS-TIM-001"]["state"] == NOT_TRACEABLE
    assert "cannot tell whether it is met" in rows["BRS-TIM-001"]["says"]
    assert account(spec(), IR)["not_traceable"] == ["BRS-TIM-001"]


def test_a_requirement_is_covered_only_by_a_record_that_exists():
    rows = {r["req_id"]: r for r in coverage(spec(), IR)}
    assert rows["BRS-EC-001"]["state"] == CONFIGURED
    assert rows["BRS-EC-002"]["state"] == NOT_CONFIGURED
    assert rows["BRS-EC-002"]["not_configured"] == ["PicklistOption"]


def test_an_external_code_traces_as_well_as_an_object_type():
    # A specification names a type; a design workbook names an instance. Either is a trace.
    s = Specification([Requirement("R1", "the ZA entity", objects=("KSA-ZA",))], [])
    assert coverage(s, IR)[0]["state"] == CONFIGURED


def test_a_requirement_naming_several_objects_needs_all_of_them():
    s = Specification([Requirement("R1", "both", objects=("LegalEntity", "PicklistOption"))], [])
    row = coverage(s, IR)[0]
    assert row["state"] == NOT_CONFIGURED
    assert row["configured"] == ["LegalEntity"] and row["not_configured"] == ["PicklistOption"]


def test_the_fit_assessment_is_the_design_authoritys_word_and_is_never_recomputed():
    rows = {r["req_id"]: r for r in coverage(spec(), IR)}
    # BRS-EC-001 is configured and still says STD, because STD is a statement about how it is met.
    assert rows["BRS-EC-001"]["fit"] == "STD" and rows["BRS-EC-001"]["state"] == CONFIGURED
    assert account(spec(), IR)["declared_gaps"] == ["BRS-TIM-001"]


def test_a_fit_value_the_platform_does_not_recognise_is_reported_not_mapped():
    s = Specification([Requirement("R1", "x", fit="PARTIAL", objects=("LegalEntity",))], [])
    assert coverage(s, IR)[0]["fit_recognised"] is False
    assert account(s, IR)["unrecognised_fit"] == ["R1"]


def test_a_requirement_citing_a_control_the_specification_never_defines_is_named():
    out = uncontrolled(spec())
    assert {"control_not_defined", "C02"} <= {out[0]["kind"], out[0]["id"]}
    assert "unassured until it does" in out[0]["says"]


def test_a_control_no_requirement_cites_is_named_too():
    s = Specification([Requirement("R1", "x")],
                      [Control("C09", "assure something", "IT", "monthly", "a report")])
    out = uncontrolled(s)
    assert [o["kind"] for o in out] == ["control_not_cited"]
    assert "assures nothing" in out[0]["says"]


def test_a_requirement_whose_control_exists_carries_its_owner_and_evidence():
    row = next(r for r in coverage(spec(), IR) if r["req_id"] == "BRS-EC-001")
    assert row["control_owner"] == "GONXT" and row["control_evidence"] == "the change log"
    assert row["control_named_but_absent"] is False


def test_the_account_publishes_no_percentage():
    out = account(spec(), IR)
    assert not any("percent" in k or "%" in str(v) for k, v in out.items() if k != "method")
    assert "No percentage is published" in out["method"]
    assert "1 of 3 requirements are described by signed intent" in out["says"]
    assert "1 name no configuration object at all" in out["says"]


def test_an_empty_specification_says_so_rather_than_reporting_everything_met():
    out = account(Specification(), [])
    assert out["says"] == "No specification has been absorbed for this engagement."
    assert out["configured"] == 0
