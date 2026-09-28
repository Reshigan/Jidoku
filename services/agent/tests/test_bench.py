"""Marking the design pass against configuration that was really built.

What these pin is the marking scheme, because the marking scheme is where a benchmark lies. Two
things matter: a case that withholds nothing is refused, and a record the pass authored that nobody
built is never counted as an error.
"""
import pytest
from jidoka_agent.bench import (Bench, BenchError, Case, ground_truth, key_of, score, withhold)

BUILT = [
    {"object": "PicklistOption", "external_code": "BASIC",
     "intent": {"externalCode": "BASIC", "label": "Basic Salary"}},
    {"object": "PicklistOption", "external_code": "HOUSING",
     "intent": {"externalCode": "HOUSING", "label": "Housing Allowance"}},
    {"object": "FOPayComponent", "external_code": "SAL",
     "intent": {"externalCode": "SAL", "name": "Salary"}},
]

PACK = {"records": BUILT, "specification": {"requirements": []}, "documents": {"SDD.docx": {}},
        "notes": ["kept"]}


def case(**kw):
    return Case(case_id="B-001", brief="design the pay component picklist",
                hide=("records",), expected=tuple(BUILT), compare=("label",), **kw)


def test_a_case_that_withholds_nothing_is_refused_because_it_measures_nothing():
    with pytest.raises(BenchError) as ex:
        Case("B-0", "design", hide=(), expected=tuple(BUILT))
    assert "the answer is in the input" in str(ex.value)


def test_a_case_with_no_right_answer_is_refused():
    with pytest.raises(BenchError):
        Case("B-0", "design", hide=("records",), expected=())


def test_a_case_naming_a_register_a_pack_does_not_have_is_refused():
    with pytest.raises(BenchError) as ex:
        Case("B-0", "design", hide=("velocity",), expected=tuple(BUILT))
    assert "not a register of a pack" in str(ex.value)


def test_withholding_removes_only_what_the_case_named_and_never_mutates_the_bundle():
    seen = withhold(PACK, ("records", "documents"))
    assert "records" not in seen and "documents" not in seen
    assert seen["notes"] == ["kept"] and "specification" in seen
    assert "records" in PACK                      # the real bundle is untouched


def test_a_record_is_identified_by_its_object_and_code_not_by_its_target_system():
    # Two runs against different tenants must still compare: the question is about the design.
    assert key_of(BUILT[0]) == "PicklistOption/BASIC"
    assert key_of({"object": "X", "intent": {"externalCode": "Y"}}) == "X/Y"
    assert key_of({"object": "DATA_MODEL_XML"}) == "DATA_MODEL_XML"


def test_a_perfect_paper_reports_matches_and_field_agreement_separately():
    got = score(case(), BUILT)
    assert got["missed"] == [] and got["extra"] == []
    assert len(got["matched"]) == 3
    # FOPayComponent has no `label`, so it is compared and agrees as absent on both sides.
    assert got["fields_agreed"] == got["fields_compared"] == 3


def test_the_right_object_with_the_wrong_value_is_not_a_pass():
    wrong = [{**BUILT[0], "intent": {"externalCode": "BASIC", "label": "Base Pay"}}, *BUILT[1:]]
    got = score(case(), wrong)
    assert len(got["matched"]) == 3
    assert got["fields_agreed"] == 2
    assert got["disagreements"] == [{"key": "PicklistOption/BASIC", "field": "label",
                                    "built": "Basic Salary", "authored": "Base Pay"}]


def test_what_the_consultants_built_and_the_pass_did_not_is_a_gap():
    got = score(case(), BUILT[:1])
    assert got["missed"] == ["FOPayComponent/SAL", "PicklistOption/HOUSING"]
    assert "were missed" in got["says"]


def test_what_the_pass_authored_and_nobody_built_is_never_counted_as_an_error():
    extra = [*BUILT, {"object": "PicklistOption", "external_code": "TRANSPORT",
                      "intent": {"externalCode": "TRANSPORT", "label": "Transport"}}]
    got = score(case(), extra)
    assert got["extra"] == ["PicklistOption/TRANSPORT"]
    assert got["missed"] == []
    # Named as needing a person, and said in words — a benchmark that scored this as wrong would
    # train the pass to author less, which is the opposite of what is wanted.
    assert "invention or something the project forgot" in got["says"]
    assert "not counted as wrong" in got["method"]


def test_comparing_no_fields_says_so_rather_than_reporting_agreement():
    got = score(Case("B-2", "design", hide=("records",), expected=tuple(BUILT)), BUILT)
    assert got["fields_compared"] == 0
    assert "says nothing about the values" in got["says"]


def test_no_single_score_is_published():
    got = score(case(), BUILT)
    assert not any("percent" in k or "score" in k or "accuracy" in k for k in got)
    assert "No single score is published" in got["method"]


def test_the_ground_truth_is_the_packs_own_records_and_can_be_narrowed():
    assert len(ground_truth(PACK)) == 3
    assert [r["external_code"] for r in ground_truth(PACK, "PicklistOption")] == \
        ["BASIC", "HOUSING"]
    assert "defects included" in ground_truth.__doc__


def test_a_bench_with_no_marked_papers_says_so_rather_than_reporting_zero():
    assert Bench().report()["says"] == "No papers have been marked."


def test_a_bench_rolls_up_every_paper_and_lists_what_needs_a_person():
    b = Bench()
    b.mark(case(), BUILT[:2])
    b.mark(Case("B-002", "again", hide=("records", "specification"), expected=(BUILT[2],),
                compare=("name",)),
           [{**BUILT[2], "intent": {"externalCode": "SAL", "name": "Base Salary"}}])
    out = b.report()
    assert out["cases"] == 2
    assert out["matched"] == 3 and out["missed"] == 1
    kinds = {d["kind"] for d in out["needs_a_person"]}
    assert kinds == {"disagreement"}
    assert any(d["field"] == "name" and d["built"] == "Salary" for d in out["needs_a_person"])


def test_the_two_kinds_of_thing_needing_a_person_are_discriminated_not_flattened():
    b = Bench()
    b.mark(case(), [*BUILT, {"object": "PicklistOption", "external_code": "TRANSPORT",
                             "intent": {"externalCode": "TRANSPORT", "label": "Transport"}}])
    rows = {d["kind"]: d for d in b.report()["needs_a_person"]}
    assert rows["authored_but_never_built"]["key"] == "PicklistOption/TRANSPORT"
    assert rows["authored_but_never_built"]["case_id"] == "B-001"
