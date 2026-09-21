"""The night shift over HTTP: it works while nobody watches and arrives with the work started."""
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


def _eng():
    eid = c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": SYSTEM, "product": "SuccessFactors", "role": "TARGET", "environment": "DEV",
        "connectivity": {"write_credentials": "vault:sf"}})
    c.post(f"/engagements/{eid}/execution/connector", json={"system_id": SYSTEM, "kind": "mock"})
    return eid


def test_the_night_reports_what_it_did_before_what_it_found():
    eid = _eng()
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert any("against the systems they bind to" in d for d in out["did"])
    assert any("control(s) over" in d for d in out["did"])
    assert out["handover"].index("**What I did**") < out["handover"].index("**What I found**")


def test_an_object_nobody_can_check_waits_for_the_morning():
    eid = _eng()
    out = c.post(f"/engagements/{eid}/nightshift").json()
    kinds = {f["kind"] for f in out["waited"] + out["deferred"]}
    assert "unconfirmable" in kinds
    assert out["interrupted"] == [], "nothing here was worth waking anybody for"


def test_a_broken_chain_is_the_one_thing_it_wakes_somebody_for():
    eid = _eng()
    STORE.get(eid).ledger.entries[0]["detail"] = "tampered after the fact"
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert [f["kind"] for f in out["interrupted"]][:1] == ["chain_broken"]
    assert "whoever can clear a halt" in out["handover"]


def test_a_half_landed_write_nobody_put_back_is_urgent():
    eid = _eng()
    STORE.get(eid).ledger.append("t", "PARTIAL", "a.builder", "2 of 5 operations failed")
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert any(f["kind"] == "partial_write" for f in out["interrupted"])


def test_a_half_landed_write_that_was_put_back_is_not_raised_again():
    eid = _eng()
    led = STORE.get(eid).ledger
    led.append("t", "PARTIAL", "a.builder", "2 of 5 operations failed")
    led.append("t", "ROLLED_BACK", "a.builder", "restored from the snapshot")
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert not any(f["kind"] == "partial_write" for f in out["interrupted"] + out["deferred"])


def test_the_budget_is_honoured_and_what_it_held_back_is_in_the_handover():
    eid = _eng()
    led = STORE.get(eid).ledger
    for i in range(4):
        led.append(f"t{i}", "PARTIAL", "a.builder", f"batch {i} half-landed")
    out = c.post(f"/engagements/{eid}/nightshift", params={"budget": 1}).json()
    assert out["budget"]["spent"] == 1 and out["budget"]["held_back"] >= 3
    assert "held" in out["handover"] and "back for this note" in out["handover"]


def test_the_handover_is_ledgered_so_the_morning_can_prove_it_happened():
    eid = _eng()
    c.post(f"/engagements/{eid}/nightshift", headers=hdr("jidoka.night", "builder"))
    entry = next(e for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]
                 if e["action"] == "HANDOVER")
    assert entry["actor"] == "jidoka.night" and "finding(s)" in entry["detail"]


def test_before_any_night_there_is_no_handover():
    eid = _eng()
    assert c.get(f"/engagements/{eid}/nightshift").json()["handover"] == ""


def test_an_auditor_may_read_the_handover_and_may_not_work_the_night():
    eid = _eng()
    c.post(f"/engagements/{eid}/nightshift")
    assert c.get(f"/engagements/{eid}/nightshift",
                 headers=hdr("an.auditor", "auditor")).status_code == 200
    assert c.post(f"/engagements/{eid}/nightshift",
                  headers=hdr("an.auditor", "auditor")).status_code == 403
