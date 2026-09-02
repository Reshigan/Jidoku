import json, pathlib
from fastapi.testclient import TestClient
from jidoka_api.main import app
from jidoka_api.routers.engagements import get_or_404

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
    # Seeded through the kernel, because that is the only thing that may write these actions.
    led = get_or_404(eid).ledger
    led.append("T1", "SNAPSHOT", "jidoka")
    led.append("T1", "EXECUTED", "alice")
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


def test_documents_project_the_engagement_over_http():
    """The document is the artefact, so it comes back as Markdown rather than in an envelope."""
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    r = c.get(f"/engagements/{eid}/documents/config-rationale")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert r.text.startswith("# Configuration Rationale")


def test_the_document_catalogue_lists_what_can_be_projected():
    ids = {d["id"] for d in c.get(f"/engagements/{_eng()}/documents").json()["documents"]}
    assert ids == {"config-rationale", "solution-design", "decision-register", "verification-report"}


def test_an_unknown_document_is_404_not_an_empty_page():
    assert c.get(f"/engagements/{_eng()}/documents/blueprint").status_code == 404
