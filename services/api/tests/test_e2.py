"""E2: lifecycle, authN/Z, persistence round-trip, offline evidence verification."""
import json
import pathlib
import threading

import pytest
from fastapi.testclient import TestClient
from jidoka_api.auth import ROLE_PERMISSIONS, issue_token
from jidoka_api.evidence import build_bundle, verify_bundle
from jidoka_api.main import app
from jidoka_api.routers.engagements import get_or_404
from jidoka_api.state import Store
from jidoka_core.repository import SqliteRepository, open_repository

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def _eng():
    return c.post("/engagements", json={"name": "E2", "client": "Komatsu"}).json()["engagement_id"]


def _hdr(subject, roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


# --- lifecycle ----------------------------------------------------------------------------------
def test_phase_advances_only_along_the_graph():
    eid = _eng()
    assert c.get(f"/engagements/{eid}").json()["phase"] == "DISCOVER"
    assert c.post(f"/engagements/{eid}/phase", json={"to": "CUTOVER"}).status_code == 409
    assert c.post(f"/engagements/{eid}/phase", json={"to": "SCOPE"}).status_code == 200
    assert c.get(f"/engagements/{eid}").json()["next_phases"] == ["BUILD"]


def test_phase_advance_is_ledgered_under_the_caller_not_a_supplied_name():
    eid = _eng()
    # "actor" is ignored: an entry naming someone who did not hold the token is a forged attestation.
    c.post(f"/engagements/{eid}/phase", json={"to": "SCOPE", "actor": "pm"})
    entries = c.get(f"/engagements/{eid}/ledger").json()["entries"]
    advanced = [e for e in entries if e["action"] == "PHASE_ADVANCED"][0]
    assert advanced["actor"] != "pm" and advanced["actor"]


def test_hypercare_is_terminal():
    eid = _eng()
    for nxt in ("SCOPE", "BUILD", "CUTOVER", "HYPERCARE"):
        assert c.post(f"/engagements/{eid}/phase", json={"to": nxt}).status_code == 200
    assert c.post(f"/engagements/{eid}/phase", json={"to": "BUILD"}).status_code == 409


# --- authN/Z ------------------------------------------------------------------------------------
def test_builder_may_never_approve():
    """Invariant 7 at the transport layer, not only in the OS capability table."""
    assert "approve" not in ROLE_PERMISSIONS["builder"]
    eid = _eng()
    r = c.post(f"/engagements/{eid}/ledger/approve", json={"task": "T1"},
               headers=_hdr("bob", ["builder"]))
    assert r.status_code == 403 and "may not 'approve'" in r.json()["detail"]


def test_auditor_may_export_but_not_write():
    eid = _eng()
    h = _hdr("ann", ["auditor"])
    assert c.get(f"/engagements/{eid}/ledger/evidence", headers=h).status_code == 200
    assert c.post(f"/engagements/{eid}/ir", json=IR, headers=h).status_code == 403


def test_bad_token_is_401():
    assert c.get("/engagements", headers={"Authorization": "Bearer not.atoken"}).status_code == 401


def test_identity_is_the_ledger_actor():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR, headers=_hdr("carol", ["builder"]))
    entries = c.get(f"/engagements/{eid}/ledger").json()["entries"]
    assert [e for e in entries if e["action"] == "LOADED"][0]["actor"] == "carol"


def test_sod_beats_role_the_same_approver_cannot_self_approve():
    """Holding the approver role is not enough: the ledger's history decides."""
    eid = _eng()
    h = _hdr("dan", ["builder", "approver"])
    c.post(f"/engagements/{eid}/ledger", json={"task": "T9", "action": "SNAPSHOT"}, headers=h)
    c.post(f"/engagements/{eid}/ledger", json={"task": "T9", "action": "EXECUTED"}, headers=h)
    assert c.post(f"/engagements/{eid}/ledger/approve", json={"task": "T9"},
                  headers=h).status_code == 403


# --- persistence --------------------------------------------------------------------------------
def test_sqlite_round_trip_rehydrates_a_cold_process(tmp_path):
    url = f"sqlite:///{tmp_path / 'j.db'}"
    s1 = Store(open_repository(url))
    e = s1.create("eid1", "Komatsu SF", "Komatsu")
    e.ledger.append("IR", "LOADED", "carol", "3 records")
    e.phase = "SCOPE"
    e.persist_header()

    s2 = Store(open_repository(url))          # a different process would see exactly this
    got = s2.get("eid1")
    assert got is not None and got.phase == "SCOPE"
    assert [x["actor"] for x in got.ledger.entries] == ["carol"]
    got.ledger.verify_chain()                 # the chain survives the round trip


def test_rehydrated_ledger_continues_the_same_chain(tmp_path):
    url = f"sqlite:///{tmp_path / 'j.db'}"
    s1 = Store(open_repository(url))
    first = s1.create("eid2", "n", "c").ledger.append("T", "SNAPSHOT", "a")
    s2 = Store(open_repository(url))
    e = s2.get("eid2")
    second = e.ledger.append("T", "EXECUTED", "a")
    assert second["prev"] == first["hash"]
    e.ledger.verify_chain()
    assert verify_bundle(e.ledger.entries)["verified"] is True


def test_concurrent_writers_share_one_connection_safely(tmp_path):
    """Regression: the connection is shared across FastAPI's threadpool (check_same_thread=False).
    Unserialised, one thread commits another's implicit transaction and the loser raises
    sqlite3.OperationalError: cannot commit - no transaction is active."""
    repo = SqliteRepository(str(tmp_path / "j.db"))
    errors: list[BaseException] = []

    def hammer(n: int) -> None:
        try:
            for i in range(40):
                repo.save_claims(f"E{n}", [{"i": i}])
                repo.append_ledger(f"E{n}", {"action": "X", "i": i})
                repo.load_claims(f"E{n}")
        except BaseException as exc:      # noqa: BLE001 - the test is what it raised
            errors.append(exc)

    threads = [threading.Thread(target=hammer, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(repo.load_ledger("E0")) == 40


def test_ledger_table_has_no_update_path(tmp_path):
    """Append-only is structural: the repository exposes append and load, nothing else."""
    repo = SqliteRepository(str(tmp_path / "j.db"))
    assert not [m for m in dir(repo) if "update" in m or "delete" in m]


# --- evidence -----------------------------------------------------------------------------------
def test_evidence_bundle_verifies_offline():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    b = c.get(f"/engagements/{eid}/ledger/evidence").json()
    assert b["bundle_version"] == "evidence/v1"
    assert b["chain"]["verification"]["verified"] is True
    assert verify_bundle(b["chain"]["entries"])["verified"] is True
    assert len(b["manifest_sha256"]) == 64


def test_evidence_detects_a_tampered_entry():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    entries = c.get(f"/engagements/{eid}/ledger/evidence").json()["chain"]["entries"]
    entries[0]["detail"] = "quietly rewritten"
    out = verify_bundle(entries)
    assert out["verified"] is False and out["broken_at"] == 0


def test_reserved_ledger_actions_cannot_be_forged_over_http():
    """Regression: invariants 4 and 6 read SNAPSHOT/EXECUTED back as preconditions. A builder who
    could post them could manufacture its own permission — forge a snapshot and a live write passes
    the rollback gate having read nothing; forge an EXECUTED under the approver's name and that
    approver is locked out of their own task."""
    eid = _eng()
    for action in ("SNAPSHOT", "EXECUTED", "APPROVED", "ARMED", "snapshot"):
        r = c.post(f"/engagements/{eid}/ledger", json={"task": "T9", "action": action})
        assert r.status_code == 403, f"{action} was accepted from a caller"
    # A free-form annotation is still allowed, and is signed by the caller, not by whoever asks.
    r = c.post(f"/engagements/{eid}/ledger",
               json={"task": "T9", "action": "NOTED", "actor": "someone-else"})
    assert r.status_code == 200 and r.json()["actor"] != "someone-else"
    assert not any(e["action"] == "SNAPSHOT" for e in get_or_404(eid).ledger.entries)


def test_evidence_attests_separation_of_duties():
    eid = _eng()
    led = get_or_404(eid).ledger
    led.append("T2", "SNAPSHOT", "bot")
    led.append("T2", "EXECUTED", "alice")
    c.post(f"/engagements/{eid}/ledger/approve", json={"task": "T2", "reviewer": "bob"})
    sod = c.get(f"/engagements/{eid}/ledger/evidence").json()["separation_of_duties"][0]
    assert sod == {"task": "T2", "approved_by": "bob", "executed_by": ["alice"],
                   "separation_held": True, "snapshot_present": True}


# --- schema -------------------------------------------------------------------------------------
def test_schema_is_published_and_validate_reports_every_error():
    s = c.get("/schema/ir").json()
    assert s["version"] == "ir/v1" and "properties" in s["schema"]
    eid = _eng()
    r = c.post(f"/engagements/{eid}/ir/validate", json=[{"object": "x"}]).json()
    assert r["loadable"] is False and len(r["errors"]["0"]) > 1
