"""The team, over HTTP: declared by the organisation, checked against the platform's own table."""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))
TEAM = [{"name": "A. Silva", "authority": ["execute", "read"], "cost": 1, "utc_offset": 2,
         "hours": [8, 16]},
        {"name": "T. Mabaso", "authority": ["approve", "resolve_dp", "read"], "cost": 4,
         "utc_offset": 2}]


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    eid = c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": IR[0]["system_binding"], "product": "SuccessFactors", "role": "TARGET",
        "environment": "DEV", "connectivity": {"write_credentials": "vault:sf"}})
    c.post(f"/engagements/{eid}/execution/connector",
           json={"system_id": IR[0]["system_binding"], "kind": "mock"})
    return eid


def test_a_team_is_declared_and_ledgered():
    eid = _eng()
    assert c.post(f"/engagements/{eid}/people", json=TEAM).status_code == 200
    out = c.get(f"/engagements/{eid}/people").json()
    assert [p["name"] for p in out["people"]] == ["A. Silva", "T. Mabaso"]
    assert "approve" in out["can_be_asked_for"]
    entry = next(e for e in c.get(f"/engagements/{eid}/ledger").json()["entries"]
                 if e["action"] == "PEOPLE_REGISTERED")
    assert "A. Silva" in entry["detail"]


def test_authority_is_checked_against_the_table_the_api_gates_on():
    """A typo would otherwise route silently to nobody."""
    eid = _eng()
    r = c.post(f"/engagements/{eid}/people",
               json=[{"name": "A. Silva", "authority": ["approves_things"]}])
    assert r.status_code == 422 and "Unknown authority" in r.json()["detail"]


def test_a_person_with_no_name_cannot_be_asked_for_anything():
    eid = _eng()
    assert c.post(f"/engagements/{eid}/people",
                  json=[{"name": "  ", "authority": ["approve"]}]).status_code == 422


def test_registering_the_team_replaces_it():
    """A team is a statement about now, not an append log."""
    eid = _eng()
    c.post(f"/engagements/{eid}/people", json=TEAM)
    c.post(f"/engagements/{eid}/people", json=[TEAM[1]])
    assert [p["name"] for p in c.get(f"/engagements/{eid}/people").json()["people"]] == ["T. Mabaso"]


def test_the_night_addresses_a_registered_person_by_name():
    eid = _eng()
    c.post(f"/engagements/{eid}/people", json=TEAM)
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert "A. Silva" in out["handover"], "the Tier-C attestation needs `execute`, which A. Silva holds"
    assert "whoever makes the change" not in out["handover"]


def test_without_a_team_the_night_still_names_the_role():
    eid = _eng()
    out = c.post(f"/engagements/{eid}/nightshift").json()
    assert "whoever makes the change" in out["handover"]


def test_a_builder_may_not_declare_the_team():
    """Setting up who the platform may ask is the same authority as registering a system."""
    eid = _eng()
    assert c.post(f"/engagements/{eid}/people", json=TEAM,
                  headers=hdr("a.reviewer", "reviewer")).status_code == 403


def test_an_auditor_may_read_the_team():
    eid = _eng()
    assert c.get(f"/engagements/{eid}/people",
                 headers=hdr("an.auditor", "auditor")).status_code == 200
