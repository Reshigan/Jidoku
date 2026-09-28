"""The specification, and the one question nobody can answer on a real engagement.

`account` is tested in the kernel. What these pin is the boundary: the trace is a judgement made by
a named person and it lives on the chain, so it survives the specification being re-registered and
it can be changed without losing what somebody said first.
"""
from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)

SPEC = {
    "requirements": [
        {"req_id": "BRS-EC-001", "requirement": "Single instance, four country layers",
         "rationale": "the baseline", "countries": "All", "wave": "W1", "fit": "STD",
         "control": "C01"},
        {"req_id": "BRS-TIM-001", "requirement": "Leave accrual by country",
         "rationale": "statute", "fit": "GAP", "control": "C02"}],
    "controls": [{"control_id": "C01", "objective": "Every change is attributable",
                  "owner": "GONXT", "frequency": "per cycle", "evidence": "the change log"}],
}

IR = [{
    "object": "PicklistOption", "product": "SuccessFactors", "system_binding": "KOM-SF-DEV",
    "external_code": "MIBCO_FLAG", "tier": "B",
    "source": {"workbook": "ZA-payroll-v3.xlsx", "signed_by": "T. Mabaso", "date": "2026-09-01"},
    "intent": {"externalCode": "MIBCO_FLAG"},
}]


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    return c.post("/engagements", json={"name": "ZA payroll",
                                        "client": "Komatsu"}).json()["engagement_id"]


def _registered():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/specification", json=SPEC, headers=hdr("the.da", "builder"))
    assert r.status_code == 200, r.text
    return eid


def test_a_specification_nobody_absorbed_is_not_an_empty_specification():
    r = c.get(f"/engagements/{_eng()}/specification", headers=hdr("reader", "auditor"))
    assert r.status_code == 404 and "not the same as one with no requirements" in r.json()["detail"]


def test_registering_records_what_the_specification_contains():
    eid = _registered()
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "SPEC_REGISTERED")
    assert entry["requirements"] == 2 and entry["controls"] == 1


def test_a_control_with_no_owner_is_refused_and_named():
    eid = _eng()
    bad = {**SPEC, "controls": [{**SPEC["controls"][0], "owner": ""}]}
    r = c.post(f"/engagements/{eid}/specification", json=bad, headers=hdr("the.da", "builder"))
    assert r.status_code == 422 and "C01" in r.json()["detail"]


def test_an_untraced_specification_reports_every_requirement_as_untraceable():
    eid = _registered()
    out = c.get(f"/engagements/{eid}/specification", headers=hdr("reader", "auditor")).json()
    assert sorted(out["not_traceable"]) == ["BRS-EC-001", "BRS-TIM-001"]
    assert out["configured"] == 0
    assert "cannot say whether they are met" in out["says"]


def test_reading_the_specification_needs_only_read():
    # Whether a programme is building what was asked for is not a privileged question.
    eid = _registered()
    assert c.get(f"/engagements/{eid}/specification",
                 headers=hdr("an.auditor", "auditor")).status_code == 200


def test_a_trace_is_a_named_persons_judgement_and_goes_on_the_chain():
    eid = _registered()
    c.post(f"/engagements/{eid}/ir", json=IR, headers=hdr("the.builder", "builder"))
    r = c.post(f"/engagements/{eid}/specification/requirements/BRS-EC-001/trace",
               json={"objects": ["PicklistOption"], "why": "agreed in the design authority"},
               headers=hdr("the.da", "builder"))
    out = r.json()
    row = next(x for x in out["requirements"] if x["req_id"] == "BRS-EC-001")
    assert row["state"] == "CONFIGURED" and row["objects"] == ["PicklistOption"]
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "REQUIREMENT_TRACED")
    assert entry["actor"] == "the.da" and entry["detail"] == "agreed in the design authority"


def test_a_trace_to_an_object_nothing_describes_yet_is_a_true_answer_not_an_error():
    eid = _registered()
    out = c.post(f"/engagements/{eid}/specification/requirements/BRS-TIM-001/trace",
                 json={"objects": ["TimeAccountType"]}, headers=hdr("the.da", "builder")).json()
    assert out["not_configured"] == ["BRS-TIM-001"]
    assert out["not_traceable"] == ["BRS-EC-001"]


def test_a_trace_to_nothing_is_refused_because_it_is_what_it_already_says():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/specification/requirements/BRS-EC-001/trace",
               json={"objects": ["  "]}, headers=hdr("the.da", "builder"))
    assert r.status_code == 422 and "a gap for the design authority to record" in r.json()["detail"]


def test_a_requirement_that_is_not_in_the_specification_cannot_be_traced():
    eid = _registered()
    r = c.post(f"/engagements/{eid}/specification/requirements/BRS-XX-999/trace",
               json={"objects": ["X"]}, headers=hdr("the.da", "builder"))
    assert r.status_code == 404


def test_the_latest_trace_wins_and_the_earlier_one_stays_in_the_record():
    eid = _registered()
    c.post(f"/engagements/{eid}/ir", json=IR, headers=hdr("the.builder", "builder"))
    for objects in (["Something"], ["PicklistOption"]):
        c.post(f"/engagements/{eid}/specification/requirements/BRS-EC-001/trace",
               json={"objects": objects}, headers=hdr("the.da", "builder"))
    out = c.get(f"/engagements/{eid}/specification", headers=hdr("reader", "auditor")).json()
    row = next(x for x in out["requirements"] if x["req_id"] == "BRS-EC-001")
    assert row["objects"] == ["PicklistOption"]
    traces = [e for e in STORE.get(eid).ledger.entries if e["action"] == "REQUIREMENT_TRACED"]
    assert [t["objects"] for t in traces] == [["Something"], ["PicklistOption"]]


def test_re_registering_the_specification_keeps_the_traces_people_made():
    eid = _registered()
    c.post(f"/engagements/{eid}/ir", json=IR, headers=hdr("the.builder", "builder"))
    c.post(f"/engagements/{eid}/specification/requirements/BRS-EC-001/trace",
           json={"objects": ["PicklistOption"]}, headers=hdr("the.da", "builder"))
    out = c.post(f"/engagements/{eid}/specification", json=SPEC,
                 headers=hdr("the.da", "builder")).json()
    row = next(x for x in out["requirements"] if x["req_id"] == "BRS-EC-001")
    assert row["state"] == "CONFIGURED"


def test_a_requirement_citing_a_control_the_specification_never_defines_is_reported():
    eid = _registered()
    out = c.get(f"/engagements/{eid}/specification", headers=hdr("reader", "auditor")).json()
    kinds = {u["id"]: u["kind"] for u in out["uncontrolled"]}
    assert kinds["C02"] == "control_not_defined"
