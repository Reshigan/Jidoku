"""The twin over HTTP: it predicts, it never blocks, and it earns its fidelity in public."""
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

R107 = {"rule_id": "R-107", "entity": "TimeType", "source": "SF rule export",
        "when": [{"field": "unit", "op": "eq", "value": "DAYS"}],
        "then": [{"field": "accrual_frequency", "op": "ne", "value": "NEVER"}]}


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng(bind=True):
    eid = c.post("/engagements", json={"name": "Twin", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": SYSTEM, "product": "SuccessFactors", "role": "TARGET", "environment": "DEV",
        "connectivity": {"write_credentials": "vault:sf"}})
    if bind:
        c.post(f"/engagements/{eid}/execution/connector", json={"system_id": SYSTEM, "kind": "mock"})
    return eid


def test_a_rule_export_reports_what_it_can_and_cannot_evaluate():
    eid = _eng()
    out = c.post(f"/engagements/{eid}/twin/rules", json={
        "rules": [R107, {"rule_id": "R-X", "entity": "TimeType",
                         "then": [{"field": "f", "op": "sounds_like"}]}],
        "source": "SF rule export 2026-02"}).json()
    assert out["evaluatable"] == 1 and out["refused"][0]["rule_id"] == "R-X"
    entry = next(e for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]
                 if e["action"] == "RULES_LOADED")
    assert entry["evaluatable"] == 1 and entry["refused"] == 1


def test_the_twin_reads_the_systems_own_metadata_not_a_supplied_schema():
    """ADR-0012: a twin calibrated against hand-fed schema measures somebody's typing."""
    eid = _eng(bind=False)
    out = c.post(f"/engagements/{eid}/twin").json()
    assert out["predictions"] == []
    assert "no binding that can read its service definition" in out["skipped"][0]["reason"]


def test_it_predicts_every_record_it_can_read_and_ledgers_each_prediction():
    eid = _eng()
    out = c.post(f"/engagements/{eid}/twin").json()
    assert {p["key"] for p in out["predictions"]}
    actions = [e for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]
               if e["action"] == "TWIN_PREDICTED"]
    assert len(actions) == len(out["predictions"])
    assert all(a["verdict"] in ("ACCEPT", "REJECT") for a in actions)


def test_a_predicted_rejection_never_blocks_anything():
    """A prediction is a model's opinion, and an opinion does not stop a signed, armed write."""
    eid = _eng()
    c.post(f"/engagements/{eid}/twin/rules", json={"rules": [
        {"rule_id": "R-STOP", "entity": "TimeType",
         "then": [{"field": "externalCode", "op": "eq", "value": "SOMETHING_ELSE"}]}]})
    out = c.post(f"/engagements/{eid}/twin").json()
    assert any(p["verdict"] == "REJECT" for p in out["predictions"])
    # the plan still builds and the step still runs
    assert c.post(f"/engagements/{eid}/plan").status_code == 200
    key = next(p["key"] for p in out["predictions"] if p["verdict"] == "REJECT")
    assert c.post(f"/engagements/{eid}/execution/execute", json={"key": key}).status_code == 200


def test_fidelity_is_withheld_until_it_has_been_earned():
    eid = _eng()
    c.post(f"/engagements/{eid}/twin")
    f = c.get(f"/engagements/{eid}/twin").json()["fidelity"]
    assert f["status"] == "UNCALIBRATED" and f["fidelity"] is None
    assert f["unsettled"] >= 1, "predictions nothing has answered yet are counted, not dropped"


def test_a_prediction_is_scored_by_what_the_substrate_actually_did():
    eid = _eng()
    c.post(f"/engagements/{eid}/twin")
    # the substrate answers for one record
    key = c.get(f"/engagements/{eid}/twin").json()["predictions"][0]["key"]
    STORE.get(eid).ledger.append(key, "VERIFIED", "a.builder", "MATCH")
    f = c.get(f"/engagements/{eid}/twin").json()["fidelity"]
    assert f["scored"] == 1 and f["agreed"] + f["disagreed"] == 1


def test_an_auditor_may_read_the_twin_and_may_not_run_it():
    eid = _eng()
    assert c.get(f"/engagements/{eid}/twin", headers=hdr("an.auditor", "auditor")).status_code == 200
    assert c.post(f"/engagements/{eid}/twin",
                  headers=hdr("an.auditor", "auditor")).status_code == 403
