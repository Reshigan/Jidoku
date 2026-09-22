"""An empty pool is a commercial decision point, not a quiet build."""
import copy
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    return c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]


def _custom(ir):
    out = copy.deepcopy(ir)
    for r in out:
        r["contract"] = {"owner": "EC"}
    return out


def test_the_pool_is_reported_beside_the_contracts_it_counts():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=_custom(IR))
    pool = c.get(f"/engagements/{eid}/contracts").json()["delta_pool"]
    assert pool["spent"] == len(IR) and pool["of"] == 30


def test_a_pool_somebody_agreed_to_is_declared_and_takes_approve():
    """The number is somebody's agreement and the platform is never the one who changes it."""
    eid = _eng()
    assert c.post(f"/engagements/{eid}/contracts/pool?size=2",
                  headers=hdr("a.builder", "builder")).status_code == 403
    out = c.post(f"/engagements/{eid}/contracts/pool?size=2",
                 headers=hdr("an.approver", "approver")).json()
    assert out["of"] == 2


def test_going_past_the_number_is_a_commercial_decision_that_halts_the_plan():
    eid = _eng()
    c.post(f"/engagements/{eid}/contracts/pool?size=1", headers=hdr("a", "approver"))
    out = c.post(f"/engagements/{eid}/ir", json=_custom(IR)).json()
    assert out["delta_pool"]["over"] == len(IR) - 1

    dp = next(d for d in c.get(f"/engagements/{eid}/decisions").json()["decision_points"]
              if d["dp_id"] == "DP-DELTA-POOL")
    assert dp["dp_type"] == "COMMERCIAL"
    assert "extend the pool" in dp["options"]
    assert c.post(f"/engagements/{eid}/plan").status_code == 409


def test_a_design_inside_its_pool_raises_nothing():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)          # no contracts: delivered standard
    out = c.get(f"/engagements/{eid}/contracts").json()
    assert out["delta_pool"]["spent"] == 0
    assert not any(d["dp_id"] == "DP-DELTA-POOL"
                   for d in c.get(f"/engagements/{eid}/decisions").json()["decision_points"])
