"""The programme domain: what a plan claims, against what the chain shows.

These tests exist because the failure mode of a plan register is a false clean — a green board over
work nobody did. So they pin the distinctions rather than the happy path: declared status is never
completion, an unresolved date never makes a gate late, and silence on a boundary condition is
reported as silence rather than as "fine".
"""
import pytest
from jidoka_core.programme import (CONDITION_BREACHED, CONDITION_CONFIRMED, GATE_PASSED, TASK_DONE,
                                   Condition, Gate, Programme, ProgrammeError, Task, account,
                                   blocked, condition_state, gate_state, task_state)


def entry(task, action, actor="ada", detail="", ts="2026-10-05T09:00:00Z"):
    return {"task": task, "action": action, "actor": actor, "detail": detail, "ts": ts}


def plan():
    return Programme(
        conditions=[Condition("DEV and QAL provisioned", "1 Oct", "Week 1 cannot start"),
                    Condition("Legacy read access", "1 Oct", "No baseline; G1 cannot pass")],
        gates=[Gate("G1", "Baseline accepted", "Fri 9 Oct", "2026-10-09", "extract accepted",
                    "baseline manifest", "Lead"),
               Gate("G3", "Hypercare entry", "week 8", "", "support model accepted", "signed RACI",
                    "IT owner")],
        tasks=[Task("T-001", "Access check", "B1", "PM", "1 Oct", "G1", (), "Complete", ""),
               Task("T-002", "Baseline extract", "B1", "Lead", "3 Oct", "G1", ("T-001",),
                    "Not started", "LegalEntity/ACME")])


def test_a_condition_requires_a_stated_consequence():
    # A boundary condition without one is a wish. The breach message quotes it, so there has to be
    # something to quote.
    with pytest.raises(ProgrammeError):
        Condition("DEV provisioned", "1 Oct", "")
    with pytest.raises(ProgrammeError):
        Condition("", "1 Oct", "slip")


def test_silence_on_a_condition_is_reported_as_silence_not_as_holding():
    states = condition_state(plan(), [])
    assert [c["holding"] for c in states] == [None, None]
    assert "nobody has said" in states[0]["says"]
    assert "Week 1 cannot start" in states[0]["says"]


def test_a_confirmed_condition_names_who_said_it_and_what_they_checked():
    chain = [entry("DEV and QAL provisioned", CONDITION_CONFIRMED, "ada", "QAL login screenshot")]
    first = condition_state(plan(), chain)[0]
    assert first["holding"] is True
    assert first["who_said"] == "ada"
    assert first["evidence"] == "QAL login screenshot"


def test_a_breach_leads_the_account_and_quotes_the_consequence():
    chain = [entry("Legacy read access", CONDITION_BREACHED, "ada", "request refused")]
    out = account(plan(), chain)
    assert out["breached_conditions"] == 1
    assert out["says"].startswith("1 boundary condition(s) have been breached")
    assert "G1 cannot pass" in out["says"]


def test_a_later_word_on_a_condition_replaces_an_earlier_one():
    chain = [entry("Legacy read access", CONDITION_CONFIRMED, "ada", "granted",
                   ts="2026-10-01T09:00:00Z"),
             entry("Legacy read access", CONDITION_BREACHED, "bo", "revoked",
                   ts="2026-10-04T09:00:00Z")]
    assert condition_state(plan(), chain)[1]["holding"] is False


def test_a_gate_nobody_passed_is_not_passed():
    g1 = gate_state(plan(), [])[0]
    assert g1["passed"] is False and g1["passed_by"] == ""
    assert g1["evidence_required"] == "baseline manifest"


def test_a_gate_is_late_only_on_a_date_that_resolved_to_a_day():
    g1, g3 = gate_state(plan(), [], today="2026-10-20")
    assert g1["late"] is True and g1["date_understood"] is True
    # "week 8" is not a day. Claiming lateness from it would be inventing a deadline.
    assert g3["late"] is False and g3["date_understood"] is False
    assert "lateness is not claimed for it" in g3["says"]


def test_no_lateness_is_claimed_when_no_today_is_given():
    assert [g["late"] for g in gate_state(plan(), [])] == [False, False]


def test_a_passed_gate_records_the_person_and_the_evidence():
    chain = [entry("G1", GATE_PASSED, "bo", "manifest sha 9f2c")]
    g1 = gate_state(plan(), chain, today="2026-10-20")[0]
    assert g1["passed"] and g1["passed_by"] == "bo" and g1["evidence_given"] == "manifest sha 9f2c"
    assert g1["late"] is False


def test_a_declared_status_is_never_completion():
    # T-001's register says "Complete" and watches nothing. The platform reports the claim as a
    # claim: this is the whole reason the domain keeps two fields.
    t1 = task_state(plan(), [])[0]
    assert t1["declared_status"] == "Complete"
    assert t1["done"] is False
    assert t1["visible_to_platform"] is False
    assert "cannot see this task" in t1["says"]


def test_a_task_that_watches_something_is_done_when_the_chain_says_so():
    t2 = task_state(plan(), [entry("LegalEntity/ACME", "EXECUTED")])[1]
    assert t2["visible_to_platform"] is True and t2["done"] is True


def test_a_person_reporting_an_invisible_task_done_is_honoured():
    t1 = task_state(plan(), [entry("T-001", TASK_DONE, "ada", "workshop held")])[0]
    assert t1["done"] is True


def test_a_dependency_the_chain_cannot_confirm_blocks_its_successor():
    waiting = blocked(plan(), [])
    assert [b["task_id"] for b in waiting] == ["T-002"]
    assert waiting[0]["waiting_on"] == ["T-001"]
    # Somebody says the workshop happened; the successor is free.
    assert blocked(plan(), [entry("T-001", TASK_DONE)]) == []


def test_a_dependency_on_something_outside_the_plan_does_not_block():
    # A register referring to a task that is not in it is a data defect, not a reason to freeze a
    # programme: it is reported by the count of tasks, never by a phantom block.
    p = Programme(tasks=[Task("T-009", "Cutover", "B4", "PM", "", "", ("T-404",), "", "")])
    assert blocked(p, []) == []


def test_the_account_publishes_no_percentage():
    out = account(plan(), [], today="2026-10-20")
    assert not any("percent" in str(k).lower() or "%" in str(v) for k, v in out.items()
                   if k != "method")
    assert "No percentage is published" in out["method"]
    assert out["gates_late"] == ["G1"]
    assert out["tasks_the_platform_cannot_see"] == 1


def test_a_clean_account_still_says_what_it_could_not_see():
    p = Programme(conditions=[Condition("DEV provisioned", "1 Oct", "slip")],
                  gates=[Gate("G1", "Baseline", "Fri 9 Oct", "2026-10-09", "c", "e", "Lead")],
                  tasks=[Task("T-001", "Extract", "B1", "Lead", "", "G1", (), "", "LE/ACME")])
    chain = [entry("DEV provisioned", CONDITION_CONFIRMED), entry("G1", GATE_PASSED, "bo", "ev"),
             entry("LE/ACME", "EXECUTED")]
    assert "1 of 1 gates passed on evidence" in account(p, chain, today="2026-10-20")["says"]


def test_a_gate_with_no_named_approver_is_a_declaration_error():
    with pytest.raises(ProgrammeError):
        Gate("G1", "Baseline", "Fri 9 Oct", "2026-10-09", "criteria", "evidence", "")
