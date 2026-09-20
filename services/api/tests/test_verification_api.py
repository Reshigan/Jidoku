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


def _key(rec):
    return f"{rec['product']}:{rec['object']}:{rec['external_code']}"


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


def test_a_record_this_platform_built_and_cannot_find_raises_a_blocking_decision_point():
    """Absence after a build is drift: we wrote it, and it is gone."""
    eid = _eng()
    _bound(eid, IR[0]["system_binding"])
    # The executor writes EXECUTED when a live write happens; the kernel is the only thing
    # permitted to (ADR-0015), so the test seeds it the same way rather than over HTTP.
    STORE.get(eid).ledger.append(_key(IR[0]), "EXECUTED", "builder@gonxt", "live write")
    body = c.post(f"/engagements/{eid}/verification").json()
    assert body["planning_blocked"] is True
    statuses = {f["key"]: f["status"] for f in body["drift"]}
    assert "MISSING" in statuses.values()
    dps = c.get(f"/engagements/{eid}/decisions").json()["decision_points"]
    assert any(d["dp_id"].startswith("DP-DRIFT-") for d in dps)
    # and planning is actually blocked by it, not just reported
    assert c.get(f"/engagements/{eid}/plan").status_code == 409


def test_a_record_nobody_has_built_yet_is_unbuilt_work_not_drift():
    """The defect this rule fixes: verifying a fresh engagement used to raise a decision point per
    record, whose two answers — reassert, or adopt — are both wrong when the answer is "build it",
    and left the plan blocked on a question nobody should have been asked (ADR-0018)."""
    eid = _eng()
    _bound(eid, IR[0]["system_binding"])
    body = c.post(f"/engagements/{eid}/verification").json()
    assert body["drift"] == [] and body["planning_blocked"] is False
    assert {u["key"] for u in body["not_applied"]} == {_key(r) for r in IR
                                                      if r["object"] != "DATA_MODEL_XML"}
    dps = c.get(f"/engagements/{eid}/decisions").json()["decision_points"]
    assert not any(d["dp_id"].startswith("DP-DRIFT-") for d in dps)
    assert c.get(f"/engagements/{eid}/plan").status_code == 200


def test_a_record_nobody_built_that_exists_anyway_is_still_drift():
    """The most interesting row on the page: somebody configured it outside this platform."""
    eid = _eng()
    conn = _bound(eid, IR[0]["system_binding"])
    row = dict(IR[0]["intent"])
    row["unit"] = "HOURS"
    conn.mock.collections.setdefault(IR[0]["object"], []).append(row)
    body = c.post(f"/engagements/{eid}/verification").json()
    assert any(f["status"] == "DRIFT" for f in body["drift"])


def test_live_state_matching_intent_is_ledgered_as_verified():
    eid = _eng()
    conn = _bound(eid, IR[0]["system_binding"])
    for rec in IR:
        conn.mock.collections.setdefault(rec["object"], []).append(dict(rec["intent"]))
    body = c.post(f"/engagements/{eid}/verification").json()
    assert body["planning_blocked"] is False
    # DATA_MODEL_XML is not an SFOData entity set, so seeding a row for it proves nothing and
    # the platform says so rather than reading a fixture it would never read in a real tenant.
    readable = [r for r in IR if r["object"] != "DATA_MODEL_XML"]
    assert len(body["verified"]) == len(readable)
    assert [u["key"] for u in body["unconfirmable"]] == ["SuccessFactors:DATA_MODEL_XML:CSDM_ZAF_NID"]
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


# --- assurance: what this engagement can prove (ADR-0023) -----------------------------------------

def test_assurance_is_empty_before_anything_claims_to_be_done():
    eid = _eng()
    a = c.get(f"/engagements/{eid}/verification/assurance").json()
    assert a["fraction"] is None and a["claimed"] == 0
    assert a["counts"] == {"unexamined": len(IR)}


def test_assurance_separates_what_was_checked_from_what_was_attested():
    eid = _eng()
    conn = _bound(eid, IR[0]["system_binding"])
    for rec in IR:
        conn.mock.collections.setdefault(rec["object"], []).append(dict(rec["intent"]))
    c.post(f"/engagements/{eid}/verification")
    a = c.get(f"/engagements/{eid}/verification/assurance").json()
    # two readable records matched; the data model has no read path and nobody has attested
    assert a["counts"]["checked"] == 2 and a["counts"]["unevidenced"] == 1
    assert a["proven"] == 2 and a["claimed"] == 3

    c.post(f"/engagements/{eid}/execution/attest",
           json={"key": "SuccessFactors:DATA_MODEL_XML:CSDM_ZAF_NID"},
           headers=hdr("t.mabaso", "builder"))
    c.post(f"/engagements/{eid}/verification")
    a = c.get(f"/engagements/{eid}/verification/assurance").json()
    assert a["counts"]["attested"] == 1 and "unevidenced" not in a["counts"]
    # the attestation did not make it provable — the denominator is unchanged
    assert a["proven"] == 2 and a["claimed"] == 3


def test_an_auditor_may_read_assurance_and_may_not_run_a_verification():
    eid = _eng()
    assert c.get(f"/engagements/{eid}/verification/assurance",
                 headers=hdr("an.auditor", "auditor")).status_code == 200
    assert c.post(f"/engagements/{eid}/verification",
                  headers=hdr("an.auditor", "auditor")).status_code == 403


def test_the_verification_report_leads_with_what_can_be_proven():
    eid = _eng()
    conn = _bound(eid, IR[0]["system_binding"])
    for rec in IR:
        conn.mock.collections.setdefault(rec["object"], []).append(dict(rec["intent"]))
    c.post(f"/engagements/{eid}/verification")
    doc = c.get(f"/engagements/{eid}/documents/verification-report").text
    assert "## What can be proven" in doc
    assert "2 of 3 records that claim to be done are proven" in doc
    # and the report does not contradict its own headline further down
    assert "unconfirmable" in doc.lower()
