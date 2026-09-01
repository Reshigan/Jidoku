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
    # Nothing in intent answers to ir:CC-01, so the ground this belief stood on is gone.
    moved = c.post(f"/engagements/{eid}/memory/{cid}/recheck")
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
    c.post(f"/engagements/{eid}/memory/{cid}/recheck")
    STORE._cache.clear()                       # cold process: rehydrate from the repository
    back = c.get(f"/engagements/{eid}/memory").json()
    assert [x["id"] for x in back["project"]] == [cid]
    assert back["project"][0]["status"] == "STALE"     # durable uncertainty survives the restart


def test_recheck_reads_the_source_and_ignores_caller_supplied_evidence():
    """The console cannot vote on whether its own belief is still true.

    A claim grounded in an IR object is TRUSTED while that object stands and STALE once it moves,
    regardless of what the caller sends — earlier this route hashed the caller's argument, so
    pressing "Re-check it" marked every verified belief stale.
    """
    from jidoka_knowledge import evidence_hash
    from jidoka_api.state import STORE
    eid = _eng()
    e = STORE.get(eid)

    class _R:                                   # the shape read_ir reads
        object, system_binding, intent, tier = "A_CostCenter", "S4", {"len": 4}, "A"
    e.ir.append(_R())
    ground = {"object": "A_CostCenter", "system_binding": "S4", "intent": {"len": 4}, "tier": "A"}

    r = c.post(f"/engagements/{eid}/memory", json={
        "subject": "cc", "text": "four digits", "source_ref": "ir:S4:A_CostCenter",
        "evidence": ground})
    cid = r.json()["id"]

    # A lie in the body must not change the verdict.
    got = c.post(f"/engagements/{eid}/memory/{cid}/recheck", json={"evidence": {"any": "rubbish"}})
    assert got.json()["status"] == "TRUSTED"

    _R.intent = {"len": 6}                      # the ground moves
    assert c.post(f"/engagements/{eid}/memory/{cid}/recheck").json()["status"] == "STALE"


def test_a_source_nobody_can_read_is_not_reported_as_drift():
    """409, not STALE: "unreadable" and "moved" are different facts about a belief."""
    eid = _eng()
    cid = c.post(f"/engagements/{eid}/memory", json={
        "subject": "payroll", "text": "monthly", "source_ref": "design:PY-02",
        "evidence": {"doc": "PY-02"}}).json()["id"]
    assert c.post(f"/engagements/{eid}/memory/{cid}/recheck").status_code == 409


# --- harvest: learning a system from its own metadata (ADR-0012) --------------------------------

def _hdr(sub="b", *roles):
    from jidoka_api.auth import issue_token
    return {"Authorization": f"Bearer {issue_token(sub, roles or ('builder',))}"}


def _harvestable(eid, system_id="LEGACY-1", role="SOURCE_LEGACY"):
    """A registered system with a read-only binding. SOURCE_LEGACY on purpose: the system most
    worth reading is the one that may never be written to."""
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": system_id, "product": "SuccessFactors", "role": role,
        "environment": "PROD", "connectivity": {}})
    r = c.post(f"/engagements/{eid}/execution/connector/reader",
               json={"system_id": system_id, "kind": "mock"}, headers=_hdr())
    assert r.status_code == 200, r.text
    return system_id


def test_a_legacy_system_can_be_read_without_ever_being_writable():
    """The bind that a harvest needs, on a system invariant 3 forbids a write connector for."""
    eid = _eng()
    sid = _harvestable(eid)
    # The ordinary write binding is still refused for the same system.
    assert c.post(f"/engagements/{eid}/execution/connector",
                  json={"system_id": sid, "kind": "mock"}, headers=_hdr()).status_code in (403, 404)


def test_harvest_forms_grounded_claims_from_the_service_definition():
    eid = _eng()
    sid = _harvestable(eid)
    r = c.post(f"/engagements/{eid}/memory/harvest", json={"system_id": sid}, headers=_hdr())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["formed"] > 0
    assert all(cl["source_ref"].startswith(f"harvest:{sid}:") for cl in body["claims"])
    # And they land in this engagement's memory, readable through the ordinary listing.
    got = c.get(f"/engagements/{eid}/memory").json()
    assert len(got["project"]) == body["formed"]


def test_a_harvested_domain_carries_the_permitted_values():
    eid = _eng()
    sid = _harvestable(eid)
    claims = c.post(f"/engagements/{eid}/memory/harvest",
                    json={"system_id": sid}, headers=_hdr()).json()["claims"]
    said = [cl["text"] for cl in claims if cl["text"].startswith("Domain ")]
    assert any("permits exactly" in t for t in said)


def test_harvest_refuses_a_system_with_no_binding():
    eid = _eng()
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": "UNBOUND", "product": "SuccessFactors", "role": "SOURCE_LEGACY",
        "environment": "PROD", "connectivity": {}})
    r = c.post(f"/engagements/{eid}/memory/harvest", json={"system_id": "UNBOUND"}, headers=_hdr())
    assert r.status_code == 409


def test_harvest_refuses_an_unregistered_system():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/memory/harvest", json={"system_id": "GHOST"}, headers=_hdr())
    assert r.status_code == 404


def test_a_harvested_claim_rechecks_against_the_same_system():
    """The round trip that makes staleness a comparison rather than an opinion."""
    eid = _eng()
    sid = _harvestable(eid)
    claims = c.post(f"/engagements/{eid}/memory/harvest",
                    json={"system_id": sid}, headers=_hdr()).json()["claims"]
    field = next(cl for cl in claims if cl["source_ref"].endswith(":fields"))
    r = c.post(f"/engagements/{eid}/memory/{field['id']}/recheck")
    assert r.status_code == 200 and r.json()["status"] == "TRUSTED"


def test_a_tier_fact_rechecks_against_the_tier_map_not_the_service_definition():
    """Tier claims have different ground; resolving them through $metadata would read as drift."""
    eid = _eng()
    sid = _harvestable(eid)
    claims = c.post(f"/engagements/{eid}/memory/harvest",
                    json={"system_id": sid}, headers=_hdr()).json()["claims"]
    tier = next(cl for cl in claims if cl["source_ref"].endswith(":tiers"))
    assert c.post(f"/engagements/{eid}/memory/{tier['id']}/recheck").json()["status"] == "TRUSTED"


def test_a_harvest_never_promotes_by_itself():
    """`offered` is a queue for a named human, not an act. System memory stays untouched."""
    eid = _eng()
    sid = _harvestable(eid)
    before = len(memory_router.SYSTEM_MEMORY.current())
    body = c.post(f"/engagements/{eid}/memory/harvest",
                  json={"system_id": sid}, headers=_hdr()).json()
    assert body["offered"] and len(body["offered"]) < body["formed"]   # settings never offered
    assert len(memory_router.SYSTEM_MEMORY.current()) == before


def test_the_harvest_is_ledgered_like_any_other_belief_write():
    eid = _eng()
    sid = _harvestable(eid)
    c.post(f"/engagements/{eid}/memory/harvest", json={"system_id": sid}, headers=_hdr())
    led = c.get(f"/engagements/{eid}/ledger").json()
    assert any(x["action"] == "READER_BOUND" for x in led["entries"])
    assert any(x["action"] == "BELIEF" for x in led["entries"])
    assert led["verified"] is True


def test_harvests_of_two_engagements_do_not_mix():
    a, b = _eng("Harvest A"), _eng("Harvest B")
    _harvestable(a, "SYS-A")
    _harvestable(b, "SYS-B")
    c.post(f"/engagements/{a}/memory/harvest", json={"system_id": "SYS-A"}, headers=_hdr())
    refs = {cl["source_ref"].split(":")[1] for cl in c.get(f"/engagements/{a}/memory").json()["project"]}
    assert refs == {"SYS-A"}
    assert c.get(f"/engagements/{b}/memory").json()["project"] == []
