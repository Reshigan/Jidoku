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


# --- the live path: the crew spends an arming it can never grant (ADR-0020) -----------------------

def _armed(eid, by="an.approver"):
    """An approver arms the target. Nothing the crew can do reaches this endpoint."""
    r = c.post(f"/engagements/{eid}/execution/arm", json={"system_id": SYSTEM, "reason": "cutover"},
               headers=hdr(by, "approver"))
    assert r.status_code == 200
    return r


def _ready(eid=None):
    eid = eid or _eng()
    _answer_the_statutory_question(eid, c.post(f"/engagements/{eid}/run").json())
    return eid


def test_with_an_approvers_arming_the_crew_configures_the_system_for_real():
    eid = _ready()
    _armed(eid)
    conn = STORE.get(eid).connectors[SYSTEM]
    before = len(conn.mock.collections.get("TimeAccountType", []))

    report = c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder")).json()

    assert {s["status"] for s in report["steps"]} == {"VERIFIED"}
    assert len(conn.mock.collections["TimeAccountType"]) == before + 1
    entries = c.get(f"/engagements/{eid}/ledger").json()["entries"]
    executed = [e for e in entries if e["action"] == "EXECUTED"]
    assert len(executed) == 2 and all(e["armed_by"] == "an.approver" for e in executed)
    assert all(e["actor"] == "a.builder" for e in executed)


def test_the_snapshot_is_on_the_chain_before_the_write_every_time():
    """Invariant 4. The executor refuses a live write without one; this proves the order held."""
    eid = _ready()
    _armed(eid)
    c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder"))
    entries = c.get(f"/engagements/{eid}/ledger").json()["entries"]
    for i, entry in enumerate(entries):
        if entry["action"] == "EXECUTED":
            assert any(e["action"] == "SNAPSHOT" and e["task"] == entry["task"]
                       for e in entries[:i]), f"{entry['task']} was written with no prior snapshot"


def test_the_crew_cannot_spend_an_arming_made_by_the_person_running_it():
    """Invariant 7 does not care that a machine is holding the keyboard in between."""
    eid = _ready()
    _armed(eid, by="same.person")
    report = c.post(f"/engagements/{eid}/run", headers=hdr("same.person", "builder")).json()
    assert {s["status"] for s in report["steps"]} == {"REFUSED"}
    assert "may not also arm it" in report["steps"][0]["detail"]
    actions = [e["action"] for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]]
    assert "EXECUTED" not in actions


def test_there_is_no_syscall_that_arms_anything():
    """The crew's ceiling is the table, not its instructions."""
    from jidoka_os.syscalls import SYSCALL_TABLE

    assert not any("arm" in name for name in SYSCALL_TABLE)


def test_an_unarmed_system_is_still_only_rehearsed_however_the_run_is_asked():
    eid = _ready()
    report = c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder")).json()
    assert {s["status"] for s in report["steps"]} == {"DRY_RUN"}


def test_what_the_crew_configured_verifies_against_the_live_system():
    eid = _ready()
    _armed(eid)
    report = c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder")).json()
    v = report["verification"]
    assert len(v["verified"]) == 2 and v["drift"] == []
    # the Tier-C record is a person's work and nobody has done it, so it is still unbuilt
    assert [u["key"] for u in v["not_applied"]] == ["SuccessFactors:DATA_MODEL_XML:CSDM_ZAF_NID"]


def test_the_crew_writes_and_still_cannot_approve_its_own_work():
    eid = _ready()
    _armed(eid)
    report = c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder")).json()
    actions = [e["action"] for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]]
    assert "APPROVED" not in actions
    assert any(w["who"] == "a reviewer who did not build it" for w in report["waiting_on_a_person"])
    # and the ledger refuses the builder's own approval when it is asked for directly
    r = c.post(f"/engagements/{eid}/ledger/approve",
               json={"task": report["steps"][0]["key"]}, headers=hdr("a.builder", "approver"))
    assert r.status_code == 403 and "may not approve" in r.json()["detail"]


# --- the transactions: on the ABAP stack a write is not done until it lands in production ---------

S4_IR = [{
    "object": "A_CostCenter", "product": "S4HANA", "system_binding": "KOM-S4-DEV", "tier": "A",
    "external_code": "0000300000",
    "intent": {"CostCenter": "0000300000", "ControllingArea": "1000", "CompanyCode": "1000",
               "CostCenterCategory": "1"},
    "source": {"workbook": "co-design-v2.xlsx", "cell_range": "A2:F2", "signed_by": "t.mabaso",
               "date": "2026-02-01"},
}]


def _abap_eng():
    """A DEV -> QA -> PROD landscape, declared by a person at registration and never inferred."""
    eid = c.post("/engagements", json={"name": "CO rollout", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=S4_IR)
    for sid, env, promotes in (("KOM-S4-PRD", "PROD", ""), ("KOM-S4-QA", "TEST", "KOM-S4-PRD"),
                               ("KOM-S4-DEV", "DEV", "KOM-S4-QA")):
        c.post(f"/engagements/{eid}/systems", json={
            "system_id": sid, "product": "S4HANA", "role": "TARGET", "environment": env,
            "connectivity": {"write_credentials": "vault:s4"}, "promotes_to": promotes})
    c.post(f"/engagements/{eid}/execution/connector",
           json={"system_id": "KOM-S4-DEV", "kind": "mock"})
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": "KOM-S4-DEV", "reason": "cutover"},
           headers=hdr("an.approver", "approver"))
    return eid


def test_the_crew_carries_an_abap_change_all_the_way_into_production():
    eid = _abap_eng()
    report = c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder")).json()

    step = report["steps"][0]
    assert step["status"] == "VERIFIED"
    assert step["transport"]["in_production"] is True
    assert step["transport"]["imported_into"] == ["KOM-S4-QA", "KOM-S4-PRD"]
    assert step["transport"]["next_hop"] is None
    # the sentence travels with the status: no row reading "not yet in production" beside a
    # transport that reached it
    assert "in production" in step["detail"] and "not yet" not in step["detail"]


def test_every_hop_is_on_the_chain_with_the_system_it_landed_in():
    eid = _abap_eng()
    c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder"))
    entries = c.get(f"/engagements/{eid}/ledger").json()["entries"]
    advanced = [e for e in entries if e["action"] == "TRANSPORT_ADVANCED"]
    assert [e["target_system"] for e in advanced] == ["KOM-S4-QA", "KOM-S4-PRD"]
    assert [e["target_environment"] for e in advanced] == ["TEST", "PROD"]
    assert advanced[-1]["in_production"] is True
    assert {e["action"] for e in entries} >= {"TRANSPORT_RELEASED", "TRANSPORT_IMPORTED"}


def test_the_crew_cannot_skip_a_hop_to_reach_production():
    """Route order is not optional, and the crew has no route of its own to propose."""
    eid = c.post("/engagements", json={"name": "CO", "client": "K"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=S4_IR)
    # DEV promotes straight into PROD: the declared route is the only one that exists.
    for sid, env, promotes in (("KOM-S4-PRD", "PROD", ""), ("KOM-S4-DEV", "DEV", "KOM-S4-PRD")):
        c.post(f"/engagements/{eid}/systems", json={
            "system_id": sid, "product": "S4HANA", "role": "TARGET", "environment": env,
            "connectivity": {"write_credentials": "vault:s4"}, "promotes_to": promotes})
    c.post(f"/engagements/{eid}/execution/connector", json={"system_id": "KOM-S4-DEV", "kind": "mock"})
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": "KOM-S4-DEV"},
           headers=hdr("an.approver", "approver"))
    report = c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder")).json()
    assert report["steps"][0]["transport"]["imported_into"] == ["KOM-S4-PRD"]


def test_a_route_that_ends_somewhere_unwritable_never_moves_the_change():
    """A landscape whose last hop may not be written to is a landscape with no route (invariant 3)."""
    eid = c.post("/engagements", json={"name": "CO", "client": "K"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=S4_IR)
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": "KOM-ECC-PRD", "product": "S4HANA", "role": "SOURCE_LEGACY",
        "environment": "PROD", "connectivity": {}})
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": "KOM-S4-DEV", "product": "S4HANA", "role": "TARGET", "environment": "DEV",
        "connectivity": {"write_credentials": "vault:s4"}, "promotes_to": "KOM-ECC-PRD"})
    c.post(f"/engagements/{eid}/execution/connector", json={"system_id": "KOM-S4-DEV", "kind": "mock"})
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": "KOM-S4-DEV"},
           headers=hdr("an.approver", "approver"))
    report = c.post(f"/engagements/{eid}/run", headers=hdr("a.builder", "builder")).json()

    step = report["steps"][0]
    assert step["status"] == "IN_TRANSPORT"
    assert "not in production" in step["detail"] or "no transport request" in step["detail"]
    entries = c.get(f"/engagements/{eid}/ledger").json()["entries"]
    assert not any(e["action"] == "TRANSPORT_ADVANCED" for e in entries)
    assert any(w["who"] == "whoever owns the transport route" for w in report["waiting_on_a_person"])
