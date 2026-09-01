"""Memory over HTTP: grounding, isolation across concurrent engagements, staleness, the gate."""
from fastapi.testclient import TestClient
from jidoka_api.main import app
from jidoka_api.routers import memory as memory_router

c = TestClient(app)


def _eng(name="Komatsu SF"):
    return c.post("/engagements", json={"name": name, "client": "Komatsu"}).json()["engagement_id"]


def _form(eid, text="cost centre codes are four-digit numeric", ev=None, subject="cost-centres"):
    return c.post(f"/engagements/{eid}/memory", json={
        "subject": subject, "text": text, "source_ref": "ir:CC-01",
        "evidence": ev if ev is not None else {"record": "CC-01"}})


def test_form_and_read_a_grounded_claim():
    eid = _eng()
    r = _form(eid)
    assert r.status_code == 200 and r.json()["status"] == "UNVERIFIED"
    got = c.get(f"/engagements/{eid}/memory").json()
    assert [x["text"] for x in got["project"]] == ["cost centre codes are four-digit numeric"]


def test_ungrounded_claim_is_refused():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/memory", json={
        "subject": "x", "text": "y", "source_ref": "", "evidence": {}})
    assert r.status_code == 422


def test_belief_write_lands_on_the_engagement_ledger():
    eid = _eng()
    _form(eid)
    led = c.get(f"/engagements/{eid}/ledger").json()
    assert any(e["action"] == "BELIEF" for e in led["entries"])
    assert led["verified"] is True          # belief writes do not break the chain


def test_concurrent_engagements_do_not_share_memory():
    a, b = _eng("Project A"), _eng("Project B")
    _form(a, "A-specific shape")
    _form(b, "B-specific shape")
    assert [x["text"] for x in c.get(f"/engagements/{a}/memory").json()["project"]] == ["A-specific shape"]
    assert [x["text"] for x in c.get(f"/engagements/{b}/memory").json()["project"]] == ["B-specific shape"]


def test_stale_claim_is_flagged_and_kept():
    eid = _eng()
    cid = _form(eid).json()["id"]
    moved = c.post(f"/engagements/{eid}/memory/{cid}/recheck", json={"evidence": {"record": "CC-99"}})
    assert moved.json()["status"] == "STALE"
    listing = c.get(f"/engagements/{eid}/memory").json()
    assert len(listing["stale"]) == 1                    # flagged, not deleted
    assert listing["counts"]["STALE"] == 1


def test_correction_supersedes_and_history_survives():
    eid = _eng()
    cid = _form(eid).json()["id"]
    r = c.post(f"/engagements/{eid}/memory/{cid}/correct", json={
        "text": "cost centre codes are five-digit numeric", "source_ref": "ir:CC-01",
        "evidence": {"record": "CC-02"}})
    assert r.status_code == 200 and r.json()["superseded"] == cid
    current = c.get(f"/engagements/{eid}/memory").json()["project"]
    assert [x["text"] for x in current] == ["cost centre codes are five-digit numeric"]
    # the superseded belief is still recorded, just closed
    old = c.get(f"/engagements/{eid}/memory/as-of", params={"when": r.json()["claim"]["valid_from"]}).json()
    assert any(x["id"] == cid for x in old["claims"]) or current[0]["supersedes"] == cid
    assert c.post(f"/engagements/{eid}/memory/{cid}/correct", json={
        "text": "again", "source_ref": "ir:CC-01", "evidence": {}}).status_code == 409


def test_promotion_refuses_client_values():
    memory_router.SYSTEM_MEMORY._claims.clear()
    eid = _eng()
    cid = _form(eid, "cost centre 1000 is the default").json()["id"]
    r = c.post(f"/engagements/{eid}/memory/{cid}/promote", json={"approver": "bob"})
    assert r.status_code == 422 and "literal numeric" in r.json()["detail"]
    assert c.get(f"/engagements/{eid}/memory").json()["system"] == []


def test_promotion_refuses_self_approval():
    memory_router.SYSTEM_MEMORY._claims.clear()
    eid = _eng()
    cid = _form(eid).json()["id"]
    builder = _form(eid, "another shape").json()["actor"]
    r = c.post(f"/engagements/{eid}/memory/{cid}/promote", json={"approver": builder})
    assert r.status_code == 422 and "may not approve" in r.json()["detail"]


def test_promoted_shape_reaches_system_memory_without_client_pointer():
    memory_router.SYSTEM_MEMORY._claims.clear()
    eid = _eng()
    cid = _form(eid).json()["id"]
    r = c.post(f"/engagements/{eid}/memory/{cid}/promote", json={"approver": "bob"})
    assert r.status_code == 200
    promoted = r.json()["promoted"]
    assert promoted["source_ref"].startswith("promotion:") and "ir:" not in promoted["source_ref"]
    # visible to a different engagement — that is the point of system memory
    other = _eng("Unrelated Client")
    assert any(x["text"] == "cost centre codes are four-digit numeric"
               for x in c.get(f"/engagements/{other}/memory").json()["system"])


def test_memory_survives_rehydration():
    """A belief that vanishes on restart is not memory. Claims persist with their badges."""
    from jidoka_api.state import STORE
    eid = _eng()
    cid = _form(eid).json()["id"]
    c.post(f"/engagements/{eid}/memory/{cid}/recheck", json={"evidence": {"record": "MOVED"}})
    STORE._cache.clear()                       # cold process: rehydrate from the repository
    back = c.get(f"/engagements/{eid}/memory").json()
    assert [x["id"] for x in back["project"]] == [cid]
    assert back["project"][0]["status"] == "STALE"     # durable uncertainty survives the restart
