"""The crew run over HTTP: what a team of consultants can do alone, and where it stops."""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))
SYSTEM = IR[0]["system_binding"]


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng(bind=True):
    eid = c.post("/engagements", json={"name": "Crew", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": SYSTEM, "product": "SuccessFactors", "role": "TARGET", "environment": "DEV",
        "connectivity": {"write_credentials": "vault:sf"}})
    if bind:
        c.post(f"/engagements/{eid}/execution/connector", json={"system_id": SYSTEM, "kind": "mock"})
    return eid


def _answer_the_statutory_question(eid, report):
    for dp in report["decisions_raised"]:
        c.post(f"/engagements/{eid}/decisions/{dp}/resolve",
               json={"value": "MONTHLY", "evidence_ref": "BCEA s20 — client legal memo"})


def test_an_engagement_with_no_intent_has_nothing_to_run():
    eid = c.post("/engagements", json={"name": "Empty", "client": "K"}).json()["engagement_id"]
    r = c.post(f"/engagements/{eid}/run")
    assert r.status_code == 409 and "no signed intent" in r.json()["detail"]


def test_the_first_run_stops_on_the_statutory_question_nobody_may_guess():
    """The sentinel finds a leave accrual signed by a workbook rather than by evidence, and the
    plan stops. This is the platform working: invariant 2 does not care who asked the question."""
    eid = _eng()
    report = c.post(f"/engagements/{eid}/run").json()
    assert report["decisions_raised"]
    assert "PLAN BLOCKED" in report["plan_blocked"]
    assert report["steps"] == []
    waiting = {w["what"] for w in report["waiting_on_a_person"]}
    assert "the run plan" in waiting


def test_once_the_question_is_answered_the_crew_takes_it_to_the_gate():
    eid = _eng()
    _answer_the_statutory_question(eid, c.post(f"/engagements/{eid}/run").json())
    report = c.post(f"/engagements/{eid}/run").json()

    assert report["plan_blocked"] is None
    assert [s["status"] for s in report["steps"]] == ["DRY_RUN", "DRY_RUN"]
    assert [a["tier"] for a in report["artefacts"]] == ["C"]
    assert report["verification"]["planning_blocked"] is False
    assert len(report["verification"]["not_applied"]) == len(IR)
    assert report["economics"]["rehearsed"] == 2 and report["economics"]["manual_steps"] == 1


def test_a_run_never_touches_the_live_system():
    """Every Tier-A step is a rehearsal because the crew cannot arm one (invariant 6)."""
    eid = _eng()
    _answer_the_statutory_question(eid, c.post(f"/engagements/{eid}/run").json())
    conn = STORE.get(eid).connectors[SYSTEM]
    before = {k: [dict(r) for r in v] for k, v in conn.mock.collections.items()}
    c.post(f"/engagements/{eid}/run")
    assert conn.mock.collections == before


def test_the_crew_writes_no_approval_and_no_execution_to_the_chain():
    """Invariant 7 read off the evidence: whatever the agents did, these two actions are absent."""
    eid = _eng()
    _answer_the_statutory_question(eid, c.post(f"/engagements/{eid}/run").json())
    c.post(f"/engagements/{eid}/run")
    actions = [e["action"] for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]]
    assert "APPROVED" not in actions and "EXECUTED" not in actions
    assert "DRY_RUN" in actions and "SNAPSHOT" in actions and "CREW_RUN" in actions


def test_a_run_is_repeatable_and_does_not_poison_the_next_one():
    """A run that left the engagement blocked by its own verification could only be run once."""
    eid = _eng()
    _answer_the_statutory_question(eid, c.post(f"/engagements/{eid}/run").json())
    first = c.post(f"/engagements/{eid}/run").json()
    second = c.post(f"/engagements/{eid}/run").json()
    assert first["plan_blocked"] is None and second["plan_blocked"] is None
    assert len(second["steps"]) == len(first["steps"])
    assert c.get(f"/engagements/{eid}/plan").status_code == 200


def test_an_approver_cannot_start_a_run():
    """A run is the builder's authority and not one permission more."""
    eid = _eng()
    r = c.post(f"/engagements/{eid}/run", headers=hdr("an.approver", "approver"))
    assert r.status_code == 403 and "may not 'execute'" in r.json()["detail"]


def test_an_auditor_can_read_the_last_run_without_starting_one():
    eid = _eng()
    c.post(f"/engagements/{eid}/run")
    r = c.get(f"/engagements/{eid}/run", headers=hdr("an.auditor", "auditor"))
    assert r.status_code == 200 and r.json()["crew"]
    assert c.post(f"/engagements/{eid}/run", headers=hdr("an.auditor", "auditor")).status_code == 403


def test_before_any_run_the_answer_is_empty_not_invented():
    eid = _eng()
    body = c.get(f"/engagements/{eid}/run").json()
    assert body["crew"] == [] and body["verification"] is None and body["plan"] is None


def test_an_unbound_system_is_reported_per_step_not_as_a_failed_run():
    eid = _eng(bind=False)
    _answer_the_statutory_question(eid, c.post(f"/engagements/{eid}/run").json())
    report = c.post(f"/engagements/{eid}/run").json()
    assert report["steps"] and all(s["status"] == "REFUSED" for s in report["steps"])
    assert all("connector" in s["detail"] or "reader" in s["detail"] or "fetcher" in s["detail"]
               for s in report["steps"])
    assert report["verification"]["skipped"]


def test_the_report_names_the_authority_each_agent_held():
    eid = _eng()
    report = c.post(f"/engagements/{eid}/run").json()
    rings = {card["name"]: card["ring"] for card in report["crew"]}
    assert rings["auditor"] == "UNTRUSTED" and rings["operator"] == "SERVICE"
    assert all("approve" not in card["capabilities"] for card in report["crew"])
