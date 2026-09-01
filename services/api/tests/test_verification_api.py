"""Verification over HTTP. The test plan is the signed IR; a mismatch is a decision, not a report."""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    eid = c.post("/engagements", json={"name": "Verify", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    return eid


def _bound(eid, system_id):
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": system_id, "product": "SuccessFactors", "role": "TARGET",
        "environment": "DEV", "connectivity": {"write_credentials": "vault:sf-write"}})
    c.post(f"/engagements/{eid}/execution/connector", json={"system_id": system_id, "kind": "mock"})
    return STORE.get(eid).connectors[system_id]


def test_no_connector_means_skipped_never_silently_green():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/verification")
    body = r.json()
    assert r.status_code == 200
    assert body["verified"] == [] and body["drift"] == []
    assert len(body["skipped"]) == len(IR)
    assert "no connector bound" in body["skipped"][0]["reason"]


def test_a_missing_record_raises_a_blocking_decision_point():
    eid = _eng()
    _bound(eid, IR[0]["system_binding"])
    body = c.post(f"/engagements/{eid}/verification").json()
    assert body["planning_blocked"] is True
    statuses = {f["key"]: f["status"] for f in body["drift"]}
    assert "MISSING" in statuses.values()
    dps = c.get(f"/engagements/{eid}/decisions").json()["decision_points"]
    assert any(d["dp_id"].startswith("DP-DRIFT-") for d in dps)
    # and planning is actually blocked by it, not just reported
    assert c.get(f"/engagements/{eid}/plan").status_code == 409


def test_live_state_matching_intent_is_ledgered_as_verified():
    eid = _eng()
    conn = _bound(eid, IR[0]["system_binding"])
    for rec in IR:
        conn.mock.collections.setdefault(rec["object"], []).append(dict(rec["intent"]))
    body = c.post(f"/engagements/{eid}/verification").json()
    assert body["planning_blocked"] is False
    assert len(body["verified"]) == len(IR)
    actions = [x["action"] for x in c.get(f"/engagements/{eid}/ledger").json()["entries"]]
    assert "VERIFIED" in actions and "DRIFT_DETECTED" not in actions


def test_drifted_values_name_the_fields_and_offer_two_honest_exits():
    eid = _eng()
    conn = _bound(eid, IR[0]["system_binding"])
    for rec in IR:
        row = dict(rec["intent"])
        conn.mock.collections.setdefault(rec["object"], []).append(row)
    conn.mock.collections["TimeAccountType"][-1]["unit"] = "HOURS"     # someone changed the tenant
    body = c.post(f"/engagements/{eid}/verification").json()
    drifted = [f for f in body["drift"] if f["status"] == "DRIFT"]
    assert drifted and "unit" in drifted[0]["fields"]
    assert drifted[0]["fields"]["unit"] == {"intent": "DAYS", "live": "HOURS"}
    dp = c.get(f"/engagements/{eid}/decisions").json()["decision_points"]
    ours = next(d for d in dp if d["dp_id"] == drifted[0]["decision_point"])
    assert any("reassert" in o for o in ours["options"])
    assert any("adopt" in o for o in ours["options"])


def test_verification_never_writes_to_the_live_system():
    eid = _eng()
    conn = _bound(eid, IR[0]["system_binding"])
    before = {k: [dict(r) for r in v] for k, v in conn.mock.collections.items()}
    c.post(f"/engagements/{eid}/verification")
    assert conn.mock.collections == before
