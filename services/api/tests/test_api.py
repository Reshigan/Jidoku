import json, pathlib
from fastapi.testclient import TestClient
from jidoka_api.main import app

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] / "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))

def _eng():
    return c.post("/engagements", json={"name": "Komatsu SF Greenfield", "client": "Komatsu"}).json()["engagement_id"]

def test_full_flow_ir_plan_ledger():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/ir", json=IR); assert r.status_code == 200
    p = c.post(f"/engagements/{eid}/plan"); assert p.status_code == 200
    assert p.json()["tier_summary"] == {"A": 2, "B": 0, "C": 1}
    ch = c.get(f"/engagements/{eid}/ledger"); assert ch.json()["verified"] is True

def test_open_dp_blocks_plan_with_409():
    eid = _eng()
    bad = json.loads(json.dumps(IR))
    bad[1]["intent"]["negative_floor"] = {"value": None, "decision_point": "DP-B11"}
    c.post(f"/engagements/{eid}/ir", json=bad)
    assert c.post(f"/engagements/{eid}/plan").status_code == 409

def test_sod_enforced_over_http():
    eid = _eng()
    c.post(f"/engagements/{eid}/ledger", json={"task": "T1", "action": "SNAPSHOT", "actor": "jidoka"})
    c.post(f"/engagements/{eid}/ledger", json={"task": "T1", "action": "EXECUTED", "actor": "alice"})
    assert c.post(f"/engagements/{eid}/ledger/approve", json={"task": "T1", "reviewer": "alice"}).status_code == 403
    assert c.post(f"/engagements/{eid}/ledger/approve", json={"task": "T1", "reviewer": "bob"}).status_code == 200

def test_source_write_lock_over_http():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/systems", json={
        "system_id": "KOM-ECC-PRD", "product": "ECC", "role": "SOURCE_LEGACY", "environment": "PROD",
        "connectivity": {"write_credentials": "vault:x"}})
    assert r.status_code == 403

def test_statutory_dp_requires_evidence():
    eid = _eng()
    c.post(f"/engagements/{eid}/decisions", json={"dp_id": "DP-B11", "dp_type": "STATUTORY",
                                                  "question": "ZA negative floor", "owner": "Komatsu HR"})
    r = c.post(f"/engagements/{eid}/decisions/DP-B11/resolve",
               json={"decided_by": "komatsu.hr", "value": "-5"})
    assert r.status_code == 403
    r = c.post(f"/engagements/{eid}/decisions/DP-B11/resolve",
               json={"decided_by": "komatsu.hr", "value": "-5", "evidence_ref": "KOM-POL-114"})
    assert r.status_code == 200
