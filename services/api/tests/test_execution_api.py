"""Execution surface over HTTP. The gates that matter are: an approver arms, a builder executes,
and neither can do the other's half."""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng_with_ir():
    eid = c.post("/engagements", json={"name": "Exec", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    return eid


def _target(eid, system_id, role="TARGET", creds="vault:sf-write"):
    return c.post(f"/engagements/{eid}/systems", json={
        "system_id": system_id, "product": "SuccessFactors", "role": role, "environment": "DEV",
        "connectivity": {"write_credentials": creds} if creds else {}})


def _first_key(eid):
    return c.get(f"/engagements/{eid}/plan").json()["steps"][0]["key"]


def _tier_a_step(eid):
    """Arming and snapshots only bite on Tier A — Tier B/C hand off to a person before any gate."""
    for s in c.get(f"/engagements/{eid}/plan").json()["steps"]:
        if s["tier"] == "A":
            return s
    raise AssertionError("fixture has no Tier-A step")


def test_builder_may_not_arm_and_approver_may_not_execute():
    """Invariants 6 and 7 at the transport layer: the two halves live in different roles."""
    eid = _eng_with_ir()
    r = c.post(f"/engagements/{eid}/execution/arm", json={"system_id": "X"}, headers=hdr("bob", "builder"))
    assert r.status_code == 403 and "may not 'arm'" in r.json()["detail"]
    r = c.post(f"/engagements/{eid}/execution/execute", json={"key": "k"}, headers=hdr("ann", "approver"))
    assert r.status_code == 403 and "may not 'execute'" in r.json()["detail"]


def test_arming_a_write_locked_system_is_refused_at_arm_time():
    eid = _eng_with_ir()
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": "LEGACY-ECC", "product": "ECC", "role": "SOURCE_LEGACY", "environment": "PROD",
        "connectivity": {}})
    r = c.post(f"/engagements/{eid}/execution/arm", json={"system_id": "LEGACY-ECC"},
               headers=hdr("ann", "approver"))
    assert r.status_code == 403


def test_arming_an_unregistered_system_is_404_not_a_silent_arm():
    eid = _eng_with_ir()
    r = c.post(f"/engagements/{eid}/execution/arm", json={"system_id": "GHOST"},
               headers=hdr("ann", "approver"))
    assert r.status_code == 404
    assert c.get(f"/engagements/{eid}/execution/arm").json()["armed"] == []


def test_unknown_product_has_no_adapter_and_is_refused():
    eid = c.post("/engagements", json={"name": "X", "client": "Y"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=[{
        "object": "Thing", "product": "Ariba", "system_binding": "A1", "tier": "A",
        "intent": {"externalCode": "T1"},
        "source": {"workbook": "WB", "signed_by": "x@y", "date": "2026-09-01"}}])
    key = _first_key(eid)
    r = c.post(f"/engagements/{eid}/execution/execute", json={"key": key})
    assert r.status_code == 422 and "No adapter registered" in r.json()["detail"]


def test_execute_unarmed_is_a_dry_run():
    eid = _eng_with_ir()
    key = _first_key(eid)
    r = c.post(f"/engagements/{eid}/execution/execute", json={"key": key})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("DRY_RUN", "HANDED_OFF")
    if body["status"] == "DRY_RUN":
        assert body["payload"]["dry_run"] is True


def test_execute_unknown_key_is_404():
    eid = _eng_with_ir()
    assert c.post(f"/engagements/{eid}/execution/execute", json={"key": "nope"}).status_code == 404


def test_armed_without_a_connector_refuses_rather_than_reporting_a_fake_success():
    """The worst possible outcome is a no-op apply reported as VERIFIED. It must be a 409."""
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    _target(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"]},
           headers=hdr("ann", "approver"))
    snap = c.post(f"/engagements/{eid}/execution/snapshot", json={"key": step["key"]},
                  headers=hdr("bob", "builder"))
    # No reader bound, so the snapshot itself refuses — an empty before-state would satisfy
    # invariant 4 without ever having read the system.
    assert snap.status_code == 409 and "cannot snapshot" in snap.json()["detail"]
    r = c.post(f"/engagements/{eid}/execution/execute", json={"key": step["key"]},
               headers=hdr("bob", "builder"))
    assert r.status_code == 409


def test_armed_write_without_a_snapshot_is_refused():
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    _target(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"]},
           headers=hdr("ann", "approver"))
    r = c.post(f"/engagements/{eid}/execution/execute", json={"key": step["key"]},
               headers=hdr("bob", "builder"))
    assert r.status_code == 409 and "snapshot" in r.json()["detail"].lower()


def test_arming_is_ledgered_and_the_chain_still_verifies():
    eid = _eng_with_ir()
    step = c.get(f"/engagements/{eid}/plan").json()["steps"][0]
    _target(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"], "reason": "cutover"},
           headers=hdr("ann", "approver"))
    chain = c.get(f"/engagements/{eid}/ledger").json()
    assert chain["verified"] is True
    armed = [e for e in chain["entries"] if e["action"] == "ARMED"]
    assert armed and armed[-1]["actor"] == "ann"


def test_disarm_removes_the_arming():
    eid = _eng_with_ir()
    step = c.get(f"/engagements/{eid}/plan").json()["steps"][0]
    _target(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"]},
           headers=hdr("ann", "approver"))
    c.delete(f"/engagements/{eid}/execution/arm/{step['system']}", headers=hdr("ann", "approver"))
    assert c.get(f"/engagements/{eid}/execution/arm").json()["armed"] == []


def test_tier_c_hands_off_even_when_armed():
    """A UI-only step is never executed by the platform, armed or not — ADR-0003."""
    eid = _eng_with_ir()
    step = next(s for s in c.get(f"/engagements/{eid}/plan").json()["steps"] if s["tier"] == "C")
    _target(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"]},
           headers=hdr("ann", "approver"))
    r = c.post(f"/engagements/{eid}/execution/execute", json={"key": step["key"]},
               headers=hdr("bob", "builder"))
    assert r.status_code == 200 and r.json()["status"] == "HANDED_OFF"


# --- connector binding: the write path a system does not have until someone gives it one -------

def _bind(eid, system_id, kind="mock", **extra):
    return c.post(f"/engagements/{eid}/execution/connector",
                  json={"system_id": system_id, "kind": kind, **extra}, headers=hdr("b", "builder"))


def test_binding_a_connector_to_a_twin_is_refused():
    """Invariant 3: a TWIN may not hold a write credential, and a connector IS one.

    Registration already refuses a TWIN that arrives holding credentials, so the case that
    reaches here is the one that matters: a credential-less TWIN someone tries to bind later."""
    eid = _eng_with_ir()
    binding = IR[0]["system_binding"]
    reg = _target(eid, binding, role="TWIN", creds="vault:sf-write")
    assert reg.status_code == 403, "a TWIN holding write credentials must fail at registration"

    _target(eid, binding, role="TWIN", creds=None)
    r = _bind(eid, binding)
    assert r.status_code == 403
    assert "TWIN" in r.json()["detail"]


def test_binding_a_connector_to_a_system_without_write_credentials_is_refused():
    eid = _eng_with_ir()
    binding = IR[0]["system_binding"]
    _target(eid, binding, creds=None)
    assert _bind(eid, binding).status_code == 403


def test_live_binding_refuses_when_the_credential_is_not_in_the_environment():
    """The refusal names the variable, never a value — there is no value to name."""
    eid = _eng_with_ir()
    binding = IR[0]["system_binding"]
    _target(eid, binding)
    r = _bind(eid, binding, kind="live", base_url="https://api.invalid",
              secret_env="JIDOKA_TEST_ABSENT")
    assert r.status_code == 422
    assert "JIDOKA_TEST_ABSENT_CLIENT_ID" in r.json()["detail"]


def test_unknown_connector_kind_is_refused_rather_than_guessed():
    eid = _eng_with_ir()
    binding = IR[0]["system_binding"]
    _target(eid, binding)
    assert _bind(eid, binding, kind="rpa").status_code == 422


def test_binding_is_ledgered():
    eid = _eng_with_ir()
    binding = IR[0]["system_binding"]
    _target(eid, binding)
    assert _bind(eid, binding).status_code == 200
    actions = [e["action"] for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]]
    assert "CONNECTOR_BOUND" in actions


def test_bound_system_can_snapshot_and_a_second_person_can_write_it_live():
    """The whole two-person path, end to end: bind, snapshot, arm as one person, write as another."""
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    binding = step["system"]
    _target(eid, binding)
    assert _bind(eid, binding).status_code == 200

    snap = c.post(f"/engagements/{eid}/execution/snapshot", json={"key": step["key"]},
                  headers=hdr("b.builder", "builder"))
    assert snap.status_code == 200, snap.text

    armed = c.post(f"/engagements/{eid}/execution/arm",
                   json={"system_id": binding, "reason": "cutover window"},
                   headers=hdr("a.approver", "approver"))
    assert armed.status_code == 200

    res = c.post(f"/engagements/{eid}/execution/execute", json={"key": step["key"]},
                 headers=hdr("b.builder", "builder"))
    assert res.status_code == 200, res.text
    assert res.json()["status"] in ("VERIFIED", "DRIFTED"), res.json()
    assert res.json()["payload"]["dry_run"] is False

    actions = [e["action"] for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]]
    for required in ("SNAPSHOT", "ARMED", "EXECUTED"):
        assert required in actions, actions


def test_an_object_with_no_declared_entity_set_is_a_refusal_not_a_server_error():
    """The IR claims tier A for an object the adapter has no honest write path to. That is the
    workbook lying about the product, so it is a 422 naming the bad tier_map entry — not a 500,
    which reads as "the platform broke" and sends the operator to the wrong place entirely.

    Caught on `AdapterError`, the shared base, so a new adapter cannot reintroduce the 500."""
    eid = c.post("/engagements", json={"name": "Exec", "client": "Komatsu"}).json()["engagement_id"]
    _target(eid, "KOM-SF-DEV")
    c.post(f"/engagements/{eid}/ir", json=[{
        "object": "PayComponent", "product": "SuccessFactors", "system_binding": "KOM-SF-DEV",
        "tier": "A", "intent": {"code": "BASIC"},
        "source": {"workbook": "w.xlsx", "signed_by": "Komatsu HR", "date": "2026-01-01"}}])
    key = _tier_a_step(eid)["key"]
    res = c.post(f"/engagements/{eid}/execution/execute", json={"key": key},
                 headers=hdr("b.builder", "builder"))
    assert res.status_code == 422, res.text
    assert "tier_map" in res.json()["detail"]


# --- rollback: restoring a prior state is a write, so it wears every gate a write wears --------

def _s4(eid, sid, role, env, promotes_to=""):
    return c.post(f"/engagements/{eid}/systems", json={
        "system_id": sid, "product": "S4HANA", "role": role, "environment": env,
        "connectivity": {"write_credentials": "vault:s4"}, "promotes_to": promotes_to})


def _abap_eng():
    """An S/4 engagement with a full DEV -> QA -> PRD route declared in the landscape."""
    eid = c.post("/engagements", json={"name": "ABAP", "client": "Komatsu"}).json()["engagement_id"]
    _s4(eid, "S4-PRD", "PROD", "PROD")
    _s4(eid, "S4-QA", "TEST", "QA", promotes_to="S4-PRD")
    _s4(eid, "S4-DEV", "DEV", "DEV", promotes_to="S4-QA")
    c.post(f"/engagements/{eid}/ir", json=[{
        "object": "A_CostCenter", "product": "S4HANA", "system_binding": "S4-DEV", "tier": "A",
        "external_code": "100000", "intent": {"CostCenter": "100000", "CompanyCode": "2000"},
        "source": {"workbook": "w.xlsx", "signed_by": "Komatsu FI", "date": "2026-01-01"}}])
    return eid, _tier_a_step(eid)["key"]


def _armed_and_written(eid, key, system, builder="b.builder"):
    """The whole legal path up to a live write: bind, snapshot, arm as one person, write as another."""
    assert _bind(eid, system).status_code == 200
    assert c.post(f"/engagements/{eid}/execution/snapshot", json={"key": key},
                  headers=hdr(builder, "builder")).status_code == 200
    assert c.post(f"/engagements/{eid}/execution/arm", json={"system_id": system, "reason": "cutover"},
                  headers=hdr("a.approver", "approver")).status_code == 200
    return c.post(f"/engagements/{eid}/execution/execute", json={"key": key}, headers=hdr(builder, "builder"))


def test_rollback_needs_execute_authority_not_merely_a_badge():
    eid = _eng_with_ir()
    r = c.post(f"/engagements/{eid}/execution/rollback", json={"key": "k"},
               headers=hdr("ann", "approver"))
    assert r.status_code == 403 and "may not 'execute'" in r.json()["detail"]


def test_rollback_of_an_unknown_key_is_404():
    eid = _eng_with_ir()
    assert c.post(f"/engagements/{eid}/execution/rollback", json={"key": "nope"},
                  headers=hdr("b", "builder")).status_code == 404


def test_rollback_without_an_armed_target_is_refused():
    """Invariant 6: a restore is a live write, so it needs an armed target exactly as an apply does."""
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    _target(eid, step["system"])
    _bind(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/snapshot", json={"key": step["key"]}, headers=hdr("b", "builder"))
    r = c.post(f"/engagements/{eid}/execution/rollback", json={"key": step["key"]},
               headers=hdr("b", "builder"))
    assert r.status_code == 403 and "not armed" in r.json()["detail"]


def test_the_person_who_armed_the_target_may_not_also_roll_it_back():
    """Invariant 7 on the rollback path — the same gate execute wears, not a weaker one."""
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    _target(eid, step["system"])
    _bind(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/snapshot", json={"key": step["key"]}, headers=hdr("b", "builder"))
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"]},
           headers=hdr("solo", "approver"))
    r = c.post(f"/engagements/{eid}/execution/rollback", json={"key": step["key"]},
               headers=hdr("solo", "builder"))
    assert r.status_code == 403 and "may not also arm" in r.json()["detail"]


def test_rollback_without_a_snapshot_is_refused_rather_than_writing_nothing():
    """Invariant 4: no snapshot, no rollback. An empty before-state restored as a success is a lie."""
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    _target(eid, step["system"])
    _bind(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"]},
           headers=hdr("a.approver", "approver"))
    r = c.post(f"/engagements/{eid}/execution/rollback", json={"key": step["key"]},
               headers=hdr("b.builder", "builder"))
    assert r.status_code == 409 and "snapshot" in r.json()["detail"].lower()


def test_rollback_against_a_write_locked_system_is_refused():
    """Invariant 3: a TWIN never holds a write path, and a restore is a write."""
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    _target(eid, step["system"])
    _bind(eid, step["system"])
    c.post(f"/engagements/{eid}/execution/snapshot", json={"key": step["key"]}, headers=hdr("b", "builder"))
    c.post(f"/engagements/{eid}/execution/arm", json={"system_id": step["system"]},
           headers=hdr("a.approver", "approver"))
    # The system is re-registered as a TWIN after the arming: the arming is stale, and the
    # registry check inside the arming gate is what has to catch it.
    _target(eid, step["system"], role="TWIN", creds=None)
    r = c.post(f"/engagements/{eid}/execution/rollback", json={"key": step["key"]},
               headers=hdr("b.builder", "builder"))
    assert r.status_code == 403 and "TWIN" in r.json()["detail"]


def test_a_live_write_can_be_put_back_and_the_rollback_is_ledgered():
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    _target(eid, step["system"])
    assert _armed_and_written(eid, step["key"], step["system"]).status_code == 200
    r = c.post(f"/engagements/{eid}/execution/rollback",
               json={"key": step["key"], "reason": "wrong pay group"}, headers=hdr("b.builder", "builder"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ROLLED_BACK"
    chain = c.get(f"/engagements/{eid}/ledger").json()
    assert chain["verified"] is True
    back = [e for e in chain["entries"] if e["action"] == "ROLLED_BACK"]
    assert back and back[-1]["actor"] == "b.builder" and back[-1]["detail"] == "wrong pay group"


# --- transport: on ABAP a step is only complete when the request reaches PROD (ADR-0006) -------

def test_transport_advance_on_a_non_abap_product_is_refused():
    eid = _eng_with_ir()
    step = _tier_a_step(eid)
    r = c.post(f"/engagements/{eid}/execution/transport", json={"key": step["key"]},
               headers=hdr("b", "builder"))
    assert r.status_code == 422 and "not an ABAP product" in r.json()["detail"]


def test_advancing_a_transport_that_was_never_created_is_404():
    eid, key = _abap_eng()
    r = c.post(f"/engagements/{eid}/execution/transport", json={"key": key}, headers=hdr("b", "builder"))
    assert r.status_code == 404 and "no transport request" in r.json()["detail"]


def test_an_abap_write_is_in_transport_and_advances_hop_by_hop_to_production():
    eid, key = _abap_eng()
    res = _armed_and_written(eid, key, "S4-DEV")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "IN_TRANSPORT", res.json()
    assert res.json()["transport"]["next_hop"] == "S4-QA"

    listed = c.get(f"/engagements/{eid}/execution/transport").json()["transports"]
    assert listed and listed[0]["next_hop"] == "S4-QA"

    qa = c.post(f"/engagements/{eid}/execution/transport", json={"key": key}, headers=hdr("b.builder", "builder"))
    assert qa.status_code == 200 and qa.json()["currently_in"] == "S4-QA"
    prd = c.post(f"/engagements/{eid}/execution/transport", json={"key": key}, headers=hdr("b.builder", "builder"))
    assert prd.status_code == 200 and prd.json()["in_production"] is True

    # Past the end of the route there is nothing left to import into.
    end = c.post(f"/engagements/{eid}/execution/transport", json={"key": key}, headers=hdr("b.builder", "builder"))
    assert end.status_code == 409 and "end of its route" in end.json()["detail"]

    chain = c.get(f"/engagements/{eid}/ledger").json()
    assert chain["verified"] is True
    advanced = [e for e in chain["entries"] if e["action"] == "TRANSPORT_ADVANCED"]
    assert [e["target_environment"] for e in advanced] == ["QA", "PROD"]
    assert "TRANSPORT_RELEASED" in [e["action"] for e in chain["entries"]]


def test_the_step_completes_only_once_the_transport_has_landed_in_production():
    eid, key = _abap_eng()
    assert _armed_and_written(eid, key, "S4-DEV").json()["status"] == "IN_TRANSPORT"
    for _ in range(2):
        c.post(f"/engagements/{eid}/execution/transport", json={"key": key}, headers=hdr("b.builder", "builder"))
    again = c.post(f"/engagements/{eid}/execution/execute", json={"key": key},
                   headers=hdr("b.builder", "builder"))
    assert again.json()["status"] == "VERIFIED", again.json()


def test_a_route_ending_in_a_write_locked_system_never_becomes_a_transport():
    """The registry, not the caller, decides the route — and it will not end at a TWIN."""
    eid = c.post("/engagements", json={"name": "ABAP", "client": "K"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": "S4-TWIN", "product": "S4HANA", "role": "TWIN", "environment": "TWIN",
        "connectivity": {}})
    _s4(eid, "S4-DEV", "DEV", "DEV", promotes_to="S4-TWIN")
    c.post(f"/engagements/{eid}/ir", json=[{
        "object": "A_CostCenter", "product": "S4HANA", "system_binding": "S4-DEV", "tier": "A",
        "external_code": "100000", "intent": {"CostCenter": "100000", "CompanyCode": "2000"},
        "source": {"workbook": "w.xlsx", "signed_by": "K", "date": "2026-01-01"}}])
    key = _tier_a_step(eid)["key"]
    res = _armed_and_written(eid, key, "S4-DEV")
    assert res.status_code == 200 and res.json()["status"] == "IN_TRANSPORT"
    # No usable route, so no request was created: the step says so rather than inventing a hop.
    assert "no transport request was supplied" in res.json()["detail"]
    assert c.post(f"/engagements/{eid}/execution/transport", json={"key": key},
                  headers=hdr("b.builder", "builder")).status_code == 404
