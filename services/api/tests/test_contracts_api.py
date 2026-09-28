"""The registry over HTTP: a projection over signed intent that stores nothing."""
import copy
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.main import app

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def _eng(ir):
    eid = c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]
    r = c.post(f"/engagements/{eid}/ir", json=ir)
    return eid, r


def test_the_komatsu_lesson_end_to_end():
    """custom-string4 is written by EC and read by Time Off, EE reporting and the payroll
    interface. As a field that is four surprises; as a contract it is one declaration."""
    ir = copy.deepcopy(IR)
    ir[0]["contract"] = {"owner": "EC",
                         "consumers": ["Time Off", "EE Reporting", "ECC Payroll"],
                         "feeds": ["ECC IT0001"], "statutory": "MIBCO main agreement"}
    eid, _ = _eng(ir)
    out = c.get(f"/engagements/{eid}/contracts").json()
    row = out["contracts"][0]
    assert row["owner"] == "EC" and "Time Off" in row["consumers"]
    assert row["statutory"] == "MIBCO main agreement"
    assert out["conflicts"] == [] and "One writer, declared readers" in out["rule"]


def test_a_contract_with_no_owner_does_not_load_at_all():
    """Structurally invalid for the same reason an unsigned source is: the thing it claims to
    establish, it does not."""
    ir = copy.deepcopy(IR)
    ir[0]["contract"] = {"consumers": ["Time Off"]}
    _, r = _eng(ir)
    assert r.status_code == 422 and "field with paperwork" in r.json()["detail"]


def test_two_writers_block_the_plan_through_the_same_gate_an_open_decision_does():
    ir = copy.deepcopy(IR)
    ir[0]["contract"] = {"owner": "EC"}
    twin = copy.deepcopy(ir[0])
    twin["contract"] = {"owner": "Time Off"}
    eid, _ = _eng(ir + [twin])
    out = c.get(f"/engagements/{eid}/contracts").json()
    assert out["conflicts"] and "One writer, declared readers" in out["conflicts"][0]["says"]
    r = c.post(f"/engagements/{eid}/plan")
    assert r.status_code == 409 and "two modules claim to write" in r.json()["detail"]


def test_an_undeclared_reader_is_reported_and_does_not_block():
    ir = copy.deepcopy(IR)
    ir[0]["contract"] = {"owner": "EC"}
    ir[1]["contract"] = {"owner": "Time Off"}
    ir[1]["depends_on"] = [f"{ir[0]['object']}:{ir[0]['intent'].get('externalCode', '?')}"]
    eid, _ = _eng(ir)
    out = c.get(f"/engagements/{eid}/contracts").json()
    assert out["undeclared_readers"] and out["conflicts"] == []
    assert c.post(f"/engagements/{eid}/plan").status_code == 200
