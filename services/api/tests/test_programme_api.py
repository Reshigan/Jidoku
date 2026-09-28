"""Running the plan: register a mobilisation pack, then answer it under the platform's own rules.

A gate is an approval, so it takes `approve`. A boundary condition is a claim, so it takes a name
and evidence. A task the chain can see is never reported done by a person. And nothing in here
publishes a percentage — which is the whole reason a programme register belongs in this platform
rather than in a spreadsheet.
"""
from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)

PLAN = {
    "conditions": [
        {"what": "DEV and QAL provisioned", "by": "1 Oct",
         "consequence": "Week 1 cannot start; day-for-day slip"},
        {"what": "Legacy read access", "by": "1 Oct", "consequence": "No baseline; G1 cannot pass"}],
    "gates": [
        {"gate_id": "G1", "name": "Baseline accepted", "date": "Fri 9 Oct",
         "due_on": "2026-10-09", "criteria": "extract accepted", "evidence": "baseline manifest",
         "approver": "Lead"},
        {"gate_id": "G3", "name": "Hypercare entry", "date": "week 8", "due_on": "",
         "criteria": "support model accepted", "evidence": "signed RACI", "approver": "IT owner"}],
    "tasks": [
        {"task_id": "T-001", "task": "Access check", "week": "B1", "owner": "PM", "gate": "G1",
         "declared_status": "Complete"},
        {"task_id": "T-002", "task": "Baseline extract", "week": "B1", "owner": "Lead",
         "gate": "G1", "depends_on": ["T-001"], "declared_status": "Not started",
         "watches": "LegalEntity/ACME"}],
}


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    return c.post("/engagements", json={"name": "ZA payroll",
                                        "client": "Komatsu"}).json()["engagement_id"]


def _registered():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/programme", json=PLAN, headers=hdr("the.pm", "builder"))
    assert r.status_code == 200, r.text
    return eid


def test_a_programme_nobody_registered_is_not_an_empty_programme():
    eid = _eng()
    r = c.get(f"/engagements/{eid}/programme", headers=hdr("reader", "auditor"))
    assert r.status_code == 404
    assert "not been given" in r.json()["detail"]


def test_registering_the_plan_records_what_it_contains():
    eid = _registered()
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "PLAN_REGISTERED")
    assert entry["tasks"] == 2 and entry["gates"] == 2 and entry["conditions"] == 2
    assert entry["actor"] == "the.pm"


def test_a_condition_with_no_stated_consequence_is_refused():
    eid = _eng()
    bad = {**PLAN, "conditions": [{"what": "DEV provisioned", "by": "1 Oct", "consequence": ""}]}
    r = c.post(f"/engagements/{eid}/programme", json=bad, headers=hdr("the.pm", "builder"))
    assert r.status_code == 422
    assert "DEV provisioned" in r.json()["detail"] and "if it fails" in r.json()["detail"]


def test_a_gate_with_no_named_approver_is_refused_and_the_gate_is_named():
    eid = _eng()
    bad = {**PLAN, "gates": [{**PLAN["gates"][0], "approver": ""}]}
    r = c.post(f"/engagements/{eid}/programme", json=bad, headers=hdr("the.pm", "builder"))
    assert r.status_code == 422 and "G1" in r.json()["detail"]


def test_an_unconfirmed_condition_leads_the_account_and_quotes_its_consequence():
    eid = _registered()
    out = c.get(f"/engagements/{eid}/programme", headers=hdr("reader", "auditor")).json()
    assert out["unspoken_conditions"] == 2
    assert "nobody has said" in out["conditions"][0]["says"]
    assert "day-for-day slip" in out["conditions"][0]["says"]


def test_confirming_a_condition_takes_a_name_and_something_that_was_checked():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/programme/conditions/confirm",
               params={"what": "DEV and QAL provisioned"}, json={"evidence": "   "},
               headers=hdr("the.pm", "builder"))
    assert r.status_code == 422 and "impression" in r.json()["detail"]

    r = c.post(f"/engagements/{eid}/programme/conditions/confirm",
               params={"what": "DEV and QAL provisioned"},
               json={"evidence": "QAL login screenshot"}, headers=hdr("the.pm", "builder"))
    out = r.json()
    assert out["unspoken_conditions"] == 1
    first = next(cd for cd in out["conditions"] if cd["what"] == "DEV and QAL provisioned")
    assert first["holding"] is True and first["who_said"] == "the.pm"


def test_a_condition_that_is_not_in_the_plan_cannot_be_confirmed():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/programme/conditions/confirm", params={"what": "something else"},
               json={"evidence": "x"}, headers=hdr("the.pm", "builder"))
    assert r.status_code == 404


def test_a_breach_carries_the_consequence_onto_the_chain():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/programme/conditions/breach",
               params={"what": "Legacy read access"}, json={"evidence": "access request refused"},
               headers=hdr("the.pm", "builder"))
    assert r.json()["breached_conditions"] == 1
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "CONDITION_BREACHED")
    assert entry["consequence"] == "No baseline; G1 cannot pass"


def test_passing_a_gate_needs_approve_not_merely_write_access():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/programme/gates/G3/pass", json={"evidence": "signed RACI"},
               headers=hdr("the.builder", "builder"))
    assert r.status_code == 403


def test_a_gate_passes_on_evidence_and_records_who_the_pack_named():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/programme/gates/G3/pass", json={"evidence": ""},
               headers=hdr("the.approver", "approver"))
    assert r.status_code == 422 and "signed RACI" in r.json()["detail"]

    r = c.post(f"/engagements/{eid}/programme/gates/G3/pass",
               json={"evidence": "RACI signed 2026-11-20", "on_behalf_of": "IT owner"},
               headers=hdr("the.approver", "approver"))
    g3 = next(g for g in r.json()["gates"] if g["gate_id"] == "G3")
    assert g3["passed"] and g3["passed_by"] == "the.approver"
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "GATE_PASSED")
    assert entry["named_approver"] == "IT owner" and entry["on_behalf_of"] == "IT owner"


def test_a_gate_will_not_pass_over_work_the_chain_says_is_outstanding():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/programme/gates/G1/pass", json={"evidence": "manifest 9f2c"},
               headers=hdr("the.approver", "approver"))
    assert r.status_code == 409
    # T-002 watches something and is not done. T-001 is invisible, so it is not held against G1.
    assert "T-002" in r.json()["detail"] and "T-001" not in r.json()["detail"]


def test_a_gate_is_late_only_once_a_date_that_resolved_has_passed():
    eid = _registered()
    out = c.get(f"/engagements/{eid}/programme", params={"today": "2026-10-20"},
                headers=hdr("reader", "auditor")).json()
    assert out["gates_late"] == ["G1"]
    g3 = next(g for g in out["gates"] if g["gate_id"] == "G3")
    assert g3["late"] is False and g3["date_understood"] is False


def test_a_person_may_report_an_invisible_task_done_and_may_not_report_a_visible_one():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/programme/tasks/T-002/done", json={"evidence": "trust me"},
               headers=hdr("the.pm", "builder"))
    assert r.status_code == 409 and "the chain answers" in r.json()["detail"]

    r = c.post(f"/engagements/{eid}/programme/tasks/T-001/done",
               json={"evidence": "access confirmed in the workshop"},
               headers=hdr("the.pm", "builder"))
    t1 = next(t for t in r.json()["tasks"] if t["task_id"] == "T-001")
    assert t1["done"] is True and t1["visible_to_platform"] is False


def test_a_dependency_blocks_its_successor_until_somebody_accounts_for_it():
    eid = _registered()
    out = c.get(f"/engagements/{eid}/programme", headers=hdr("reader", "auditor")).json()
    assert [b["task_id"] for b in out["blocked"]] == ["T-002"]
    c.post(f"/engagements/{eid}/programme/tasks/T-001/done", json={"evidence": "workshop held"},
           headers=hdr("the.pm", "builder"))
    out = c.get(f"/engagements/{eid}/programme", headers=hdr("reader", "auditor")).json()
    assert out["blocked"] == []


def test_the_read_publishes_no_percentage_complete():
    eid = _registered()
    out = c.get(f"/engagements/{eid}/programme", headers=hdr("reader", "auditor")).json()
    assert "No percentage is published" in out["method"]
    assert out["tasks_the_platform_cannot_see"] == 1
    assert not any("percent" in k for k in out)


def test_re_registering_replaces_the_plan_rather_than_appending_to_it():
    eid = _registered()
    smaller = {**PLAN, "tasks": [PLAN["tasks"][0]]}
    out = c.post(f"/engagements/{eid}/programme", json=smaller,
                 headers=hdr("the.pm", "builder")).json()
    assert len(out["tasks"]) == 1
    # And what was already answered stays answered: the register is a statement about now, the
    # chain is the record of what happened.
    assert len([e for e in STORE.get(eid).ledger.entries
                if e["action"] == "PLAN_REGISTERED"]) == 2
