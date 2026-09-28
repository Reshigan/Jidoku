"""Absorbing a mobilisation pack.

The fixtures reproduce a real pack's shape with invented values: a three-row banner above the
header, registers under four different headers, dates in prose, and a term that crosses a year
boundary. The real pack is client material and is never committed; `fixtures/make_fixtures.py`
builds these.

What is pinned here is what the absorber must never do quietly: read some sheets and report the
result as the whole pack, resolve a date it cannot resolve, or let a register's claim through as a
fact.
"""
from pathlib import Path

from jidoka_compiler.absorb import (Absorbed, absorb_alignment, absorb_document, absorb_plan,
                                    duplicates, merge, resolve_date, set_term)

FIX = Path(__file__).parent / "fixtures"
PLAN = FIX / "mobilisation_plan.xlsx"
MATRIX = FIX / "alignment_matrix.xlsx"


def plan():
    set_term(2026, 10)
    return absorb_plan(PLAN, 2026, 2027)


def test_a_date_needs_a_day_and_a_month_or_it_does_not_resolve():
    assert resolve_date("Fri 9 Oct", 2026) == "2026-10-09"
    assert resolve_date("27 Nov", 2026) == "2026-11-27"
    assert resolve_date("week 8", 2026) == ""
    assert resolve_date("", 2026) == ""
    assert resolve_date("October", 2026) == ""          # a month with no day is not a day
    assert resolve_date("31 Feb", 2026) == ""           # not a real date, so not a date


def test_a_month_before_the_terms_start_belongs_to_the_following_year():
    # The pack runs 1 Oct to 8 Jan. A January date filed under 2026 would sit eleven months in the
    # past and every gate after it would read as late.
    set_term(2026, 10)
    assert resolve_date("8 Jan", 2026, 2027) == "2027-01-08"
    assert resolve_date("9 Oct", 2026, 2027) == "2026-10-09"


def test_the_header_is_found_under_the_banner():
    # Row 5, not row 1. A reader anchored to the first row reports a pack as empty and says nothing.
    p = plan()
    assert [t["task_id"] for t in p.tasks][:3] == ["T-001", "T-002", "T-003"]
    assert p.tasks[0]["owner"] == "PM"
    assert p.tasks[0]["week"] == "B1"


def test_a_dependency_list_survives_both_separators():
    t3 = next(t for t in plan().tasks if t["task_id"] == "T-003")
    assert t3["depends_on"] == ("T-002", "T-001")


def test_the_register_status_is_absorbed_as_a_claim_not_as_completion():
    t3 = next(t for t in plan().tasks if t["task_id"] == "T-003")
    assert t3["declared_status"] == "Complete"
    assert t3["watches"] == ""      # nothing to watch, so the platform will report the claim as one


def test_gates_carry_their_prose_date_and_only_a_resolvable_iso_one():
    gates = {g["gate_id"]: g for g in plan().gates}
    assert gates["G1"]["due_on"] == "2026-10-09" and gates["G1"]["date"] == "Fri 9 Oct"
    assert gates["G3"]["due_on"] == "" and gates["G3"]["date"] == "week 8"
    assert gates["G1"]["approver"] == "Lead + client IT owner"


def test_the_knowledge_transfer_tracker_is_absorbed_as_tasks():
    # A different header on a different sheet, and still a task register. Leaving it out would
    # report a transition plan with no transition in it.
    k1 = next(t for t in plan().tasks if t["task_id"] == "KT-K1")
    assert k1["owner"] == "Lead" and k1["week"] == "B1"
    assert "baseline extract" in k1["task"]


def test_deliverables_are_absorbed_as_gates_because_somebody_accepts_them():
    gates = {g["gate_id"]: g for g in plan().gates}
    assert gates["DEL-D1"]["approver"] == "Client IT owner"
    assert gates["DEL-D1"]["due_on"] == "2026-11-27"
    # "8 Jan" is in the term's following year.
    assert gates["DEL-D2"]["due_on"] == "2027-01-08"


def test_every_sheet_not_absorbed_is_named():
    notes = " ".join(plan().notes)
    assert "Summary" in notes
    assert "not absorbed" in notes


def test_the_counts_are_stated_and_so_are_the_dates_that_did_not_resolve():
    p = plan()
    notes = " ".join(p.notes)
    assert f"{len(p.tasks)} task(s)" in notes and f"{len(p.gates)} gate(s)" in notes
    assert "1 gate date(s) did not resolve" in notes


def test_decisions_are_registered_as_design_and_the_retyping_is_said_out_loud():
    p = plan()
    design = [d for d in p.decisions if d["dp_type"] == "DESIGN"]
    assert [d["dp_id"] for d in design] == ["DP-B01", "DP-B02"]
    # DP-B02 is a pay frequency — plausibly statutory. The absorber cannot know, and says so
    # rather than typing it and letting a STATUTORY answer resolve without evidence.
    assert "re-typed by a person" in " ".join(p.notes)


def test_conditions_carry_the_consequence_the_pack_wrote_down():
    conds = plan().conditions
    assert len(conds) == 2
    assert conds[0]["consequence"] == "Week 1 cannot start; day-for-day slip"
    assert all(c["consequence"] for c in conds)


def test_an_approverless_gate_is_named_rather_than_dropped(tmp_path):
    from openpyxl import load_workbook
    wb = load_workbook(PLAN)
    ws = wb["Gates"]
    ws.cell(row=6, column=6).value = None      # G1 loses its approver
    out = tmp_path / "no_approver.xlsx"
    wb.save(out)
    notes = " ".join(absorb_plan(out, 2026, 2027).notes)
    assert "G1" in notes and "name no approver" in notes
    assert "Fix the workbook, not the load" in notes


def test_the_alignment_matrix_gives_the_contract_registry_owners_and_readers():
    a = absorb_alignment(MATRIX)
    assert a.contracts["Employment and job information"]["owner"] == "EC"
    assert a.contracts["Employment and job information"]["consumers"] == \
        ["All modules", "ECC", "Analytics"]
    assert a.contracts["Pay components"]["consumers"] == ["EC", "Analytics"]


def test_interlocks_carry_the_failure_mode_the_design_authority_stated():
    a = absorb_alignment(MATRIX)
    # In their own register, never among the records: `records` is signed-intent-shaped, and a
    # bundle whose records cannot be posted to /ir has a decorative block where its design should be.
    assert a.records == []
    assert [r["interlock"] for r in a.interlocks] == ["I-01", "I-02"]
    assert "stale master data" in a.interlocks[0]["failure_mode"]
    assert all(r["failure_mode"] for r in a.interlocks)
    assert "interlock(s) with a stated failure mode" in " ".join(a.notes)


def test_a_sheet_the_pack_does_not_have_is_absent_rather_than_fatal():
    # A pack is not one shape. A missing register yields nothing and the counts say so.
    a = absorb_alignment(PLAN)
    assert a.contracts == {} and a.records == [] and a.interlocks == []


def test_a_sheet_holding_two_registers_is_read_as_two_registers():
    # The Gates sheet carries five gates, a blank row, a caption and then the one-way doors under
    # their own header. Reading to the bottom of the sheet turned the caption and the second header
    # row into gates and lost the doors — which are the entries that need two approvers.
    p = plan()
    assert [g["gate_id"] for g in p.gates if not g["gate_id"].startswith("DEL-")] == \
        ["G1", "G2", "G3"]
    assert "One-way doors" not in [g["name"] for g in p.gates]
    assert [d["door_id"] for d in p.doors] == ["DOOR-D1", "DOOR-D2"]


def test_a_one_way_door_is_a_one_way_decision_and_never_a_gate():
    p = plan()
    doors = {d["dp_id"]: d for d in p.decisions if d["dp_type"] == "ONE_WAY"}
    assert set(doors) == {"DOOR-D1", "DOOR-D2"}
    # A deliverable and a door both numbered from one is normal in a pack. Sharing a ledger key is
    # not: one register's answer would resolve the other's entry.
    assert not set(doors) & {g["gate_id"] for g in p.gates}
    assert "ONE_WAY decisions, not as gates" in " ".join(p.notes)


def test_a_door_naming_one_person_is_named_as_one_that_cannot_be_resolved():
    p = plan()
    assert next(d for d in p.doors if d["door_id"] == "DOOR-D1")["approvers"] == ["Lead"]
    assert next(d for d in p.doors if d["door_id"] == "DOOR-D2")["approvers"] == \
        ["Load lead", "client IT"]
    notes = " ".join(p.notes)
    assert "DOOR-D1" in notes and "fewer than two approvers" in notes
    assert "the rule working, not" in notes


def test_a_caption_is_not_a_register():
    from jidoka_compiler.absorb import _blocks
    headers = [b["header"][0] for b in _blocks(PLAN, "Gates")]
    assert headers == ["Gate", "#"]      # not "One-way doors"


def test_no_two_absorbed_entries_share_a_ledger_key():
    p = plan()
    ids = ([g["gate_id"] for g in p.gates] + [t["task_id"] for t in p.tasks]
           + [d["door_id"] for d in p.doors])
    assert len(ids) == len(set(ids))
    assert "register prefixes applied" in " ".join(p.notes)


# --------------------------------------------------------------------------------------------
# The design documents. A pack read as workbooks alone is two thirds of a design: on the real one
# the Word files carry sixty-two requirements, fifteen control objectives, seventeen decisions
# that appear in no workbook, eleven ordering constraints and twenty-one design rules.
DOC = FIX / "design_document.docx"
LIC = FIX / "licensing_position.docx"


def doc():
    return absorb_document(DOC)


def test_a_specification_arrives_with_its_fit_assessment_and_its_control():
    reqs = {r["req_id"]: r for r in doc().requirements}
    assert set(reqs) == {"BRS-EC-001", "BRS-EC-002", "BRS-TIM-001"}
    assert reqs["BRS-EC-001"]["fit"] == "STD" and reqs["BRS-EC-001"]["control"] == "C01"
    assert reqs["BRS-TIM-001"]["fit"] == "GAP"
    # Nothing is traced at absorption: which objects satisfy a requirement is a judgement about a
    # client's design, and guessing it would report the specification as met.
    assert all(r["objects"] == () for r in doc().requirements)


def test_a_control_objective_arrives_with_its_owner_frequency_and_evidence():
    c = doc().controls[0]
    assert c["control_id"] == "C01" and c["owner"] == "GONXT (execution)"
    assert c["frequency"] == "Per load cycle" and c["evidence"] == "Evidence bundle per cycle"


def test_a_design_dependency_is_a_decision_the_design_is_already_running_on():
    # The document states an interim position and the streams build against it. That is a decision
    # with an answer nobody signed.
    dps = {d["dp_id"]: d for d in doc().decisions}
    assert dps["DP-B01"]["question"] == "Provisioning access"
    assert dps["DP-B01"]["options"] == ["No interim position available"]
    assert dps["DP-C04"]["owner"] == "Steering committee"
    assert all(d["dp_type"] == "DESIGN" for d in doc().decisions)


def test_ordering_constraints_carry_why_and_what_stalls():
    o = doc().ordering[0]
    assert o["by"] == "Week 1" and "cleansing rules" in o["because"]
    assert o["stalls"] == "The whole migration"


def test_rules_and_principles_are_kept_apart_and_both_say_what_they_prevent():
    rules = {r["rule_id"]: r for r in doc().rules}
    assert rules["P1"]["kind"] == "principle" and rules["A1"]["kind"] == "rule"
    assert "Checked at G2 and nightly" in rules["A1"]["why"]


def test_the_document_carries_the_alignment_matrix_too():
    assert doc().contracts["Employment and job information"]["owner"] == "EC"
    assert doc().contracts["Employment and job information"]["consumers"] == ["All modules", "ECC"]


def test_a_document_reports_what_it_did_not_read_including_the_prose():
    notes = " ".join(doc().notes)
    assert "table(s) were not read" in notes and "Document ID" in notes
    assert "section(s) of prose were not read at all" in notes


def test_the_same_decision_stated_two_ways_across_a_pack_is_named_not_reconciled():
    pack = Absorbed()
    merge(pack, absorb_document(DOC))
    merge(pack, absorb_document(LIC))
    found = duplicates(pack)
    assert len(found) == 1 and "DP-C04" in found[0]
    # It does not claim one is wrong. On the real pack most divergences are an editorial reword,
    # and a reader who is told "one of these is out of date" goes looking for a defect that is not
    # there — while the thing that is true, that they get whichever copy they open, goes unsaid.
    assert "nothing here can tell" in found[0]
    assert "answer the statement they were shown" in found[0]
    # Both are kept. Choosing between them is the design authority's job, not a reader's.
    assert len([d for d in pack.decisions if d["dp_id"] == "DP-C04"]) == 2


def test_the_same_statement_wrapped_differently_is_not_a_divergence():
    from jidoka_compiler.absorb import duplicates as dups
    pack = Absorbed(decisions=[{"dp_id": "DP-1", "question": "Variable Pay in scope?"},
                               {"dp_id": "DP-1", "question": "Variable   Pay\n in scope?"}])
    assert dups(pack) == []


def test_a_pack_that_restates_a_decision_identically_is_not_a_defect():
    pack = Absorbed()
    merge(pack, absorb_document(DOC))
    merge(pack, absorb_document(DOC))
    assert duplicates(pack) == []


def test_merge_carries_every_register_including_the_one_way_doors():
    # Written out field by field once, and it dropped the doors — the entries that need two
    # approvers. The test is here so the next field added is not lost the same way.
    pack, other = Absorbed(), plan()
    merge(pack, other)
    for name in ("records", "decisions", "conditions", "gates", "doors", "tasks", "requirements",
                 "controls", "ordering", "rules", "interlocks", "scope", "notes"):
        assert len(getattr(pack, name)) == len(getattr(other, name)), name


def test_a_file_that_is_not_a_document_is_named_rather_than_raising():
    out = absorb_document(FIX / "mobilisation_plan.xlsx")
    assert out.requirements == [] and "not a readable .docx" in " ".join(out.notes)
