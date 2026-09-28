"""A new design supersedes the old one; it does not quietly replace it.

The failure this exists for: a record executed against a customer's system, then dropped from the
next workbook, vanishing from verification, assurance and drift while the change sits in their
tenant with nothing claiming it.
"""
import copy
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def _eng():
    return c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]


def test_the_chain_records_what_the_new_version_did_to_the_old_one():
    """"47 records" is not a design history."""
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    changed = copy.deepcopy(IR)
    changed[0]["intent"]["name"] = "renamed by v2"
    out = c.post(f"/engagements/{eid}/ir", json=changed[:-1]).json()

    assert out["superseded"]["changed"] and out["superseded"]["removed"]
    supersedes = [e for e in STORE.get(eid).ledger.entries if e["action"] == "SUPERSEDED"]
    assert len(supersedes) == 1, "a first load adds every record and supersedes nothing"
    entry = supersedes[-1]
    assert "removed" in entry["detail"] and entry["removed"] == out["superseded"]["removed"]


def test_a_live_record_the_new_design_drops_is_not_allowed_to_disappear():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    dropped = STORE.get(eid).ir[-1].key
    STORE.get(eid).ledger.append(dropped, "EXECUTED", "a.builder", "wrote it to the tenant")

    out = c.post(f"/engagements/{eid}/ir", json=IR[:-1]).json()
    assert [o["key"] for o in out["orphaned"]] == [dropped]
    assert "still there and nothing claims it" in out["orphaned"][0]["says"]


def test_an_orphan_halts_planning_with_two_exits_and_no_third():
    """Drift's treatment, because it is drift's sibling: JIDOKA will not plan around a change
    nobody claims, and it will not choose which way to resolve it either."""
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    dropped = STORE.get(eid).ir[-1].key
    STORE.get(eid).ledger.append(dropped, "EXECUTED", "a.builder", "wrote it to the tenant")
    c.post(f"/engagements/{eid}/ir", json=IR[:-1])

    dp = next(d for d in c.get(f"/engagements/{eid}/decisions").json()["decision_points"]
              if d["dp_id"] == f"DP-ORPHAN-{dropped}")
    assert dp["dp_type"] == "DESIGN"
    assert sorted(dp["options"]) == ["re-sign it into the design", "take it out of the system"]
    assert c.post(f"/engagements/{eid}/plan").status_code == 409


def test_a_record_that_was_rolled_back_is_not_an_orphan():
    """The platform already cleaned up after itself; chasing it would be the platform nagging
    about work it did."""
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    dropped = STORE.get(eid).ir[-1].key
    led = STORE.get(eid).ledger
    led.append(dropped, "EXECUTED", "a.builder", "wrote it")
    led.append(dropped, "ROLLED_BACK", "a.builder", "put it back")
    assert c.post(f"/engagements/{eid}/ir", json=IR[:-1]).json()["orphaned"] == []


def test_a_record_nothing_ever_touched_is_dropped_without_ceremony():
    """A design that changed its mind before anything was built owes nobody an explanation."""
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    out = c.post(f"/engagements/{eid}/ir", json=IR[:-1]).json()
    assert out["orphaned"] == [] and out["superseded"]["removed"]


def test_the_night_shift_chases_an_orphan_so_nobody_has_to_open_the_console():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    dropped = STORE.get(eid).ir[-1].key
    STORE.get(eid).ledger.append(dropped, "EXECUTED", "a.builder", "wrote it")
    c.post(f"/engagements/{eid}/ir", json=IR[:-1])

    night = c.post(f"/engagements/{eid}/nightshift").json()
    rows = night["interrupted"] + night["waited"] + night["deferred"]
    found = next(f for f in rows if f["kind"] == "orphaned")
    assert dropped in found["what"] and found["cost"] == 85
