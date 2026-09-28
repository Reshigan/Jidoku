"""Insight over HTTP, and the journey it exists to open.

The load-bearing test here is the last one. Archaeology is only worth building if a recovered
object can become ordinary configuration — planned, documented and verified by the machinery
that already exists — without archaeology knowing anything about any of it.
"""
from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
SYSTEM = "KOM-SF-LEGACY"


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng(role="SOURCE_LEGACY", connectivity=None):
    eid = c.post("/engagements", json={"name": "Brownfield", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": SYSTEM, "product": "SuccessFactors", "role": role,
        "environment": "PRD", "connectivity": connectivity or {}})
    # A legacy system may never hold a write credential (invariant 3), so archaeology reads it
    # through a binding that has no write half at all.
    c.post(f"/engagements/{eid}/execution/connector/reader",
           json={"system_id": SYSTEM, "kind": "mock"})
    return eid


def _dig(eid, entities=("FOCostCenter",)):
    return c.post(f"/engagements/{eid}/insight/archaeology",
                  json={"system_id": SYSTEM, "entities": list(entities)})


def test_archaeology_recovers_objects_and_leaves_them_unsigned():
    eid = _eng()
    body = _dig(eid).json()
    assert len(body["drafts"]) == 3
    assert all(d["source"]["signed_by"] == "" for d in body["drafts"])
    assert len(body["unexplained"]) == 3        # nothing recovered carries a rationale
    # recovered is not configured: IR is still empty, so there is nothing to plan
    assert c.get(f"/engagements/{eid}/ir").json()["records"] == []


def test_reading_an_unbound_system_is_refused_not_guessed():
    eid = c.post("/engagements", json={"name": "B", "client": "K"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": SYSTEM, "product": "SuccessFactors", "role": "SOURCE_LEGACY",
        "environment": "PRD", "connectivity": {}})
    r = _dig(eid)
    assert r.status_code == 409 and "no binding" in r.json()["detail"]


def test_a_read_only_binding_still_cannot_write():
    """Invariant 3: archaeology reads the systems that may never be written to."""
    eid = _eng()
    _dig(eid)
    binding = STORE.get(eid).connectors[SYSTEM]
    try:
        binding.apply({"kind": "odata_batch", "operations": [{"entity": "FOCostCenter"}]})
        raise AssertionError("a read-only binding wrote")
    except Exception as ex:
        assert "no write path" in str(ex)


def test_re_digging_replaces_that_systems_drafts_rather_than_duplicating():
    eid = _eng()
    _dig(eid)
    body = _dig(eid).json()
    assert len(body["drafts"]) == 3


def test_signing_is_written_by_the_act_not_claimed_by_the_caller():
    """ADR-0015: the signature is the authenticated caller's, and there is no field to override it."""
    eid = _eng()
    keys = [d["key"] for d in _dig(eid).json()["drafts"]][:1]
    body = c.post(f"/engagements/{eid}/insight/archaeology/sign",
                  json={"keys": keys, "workbook": "brownfield-review-2026"},
                  headers=hdr("lead@client", "builder")).json()
    rec = next(r for r in c.get(f"/engagements/{eid}/ir").json()["records"] if r["key"] == keys[0])
    assert rec["source"]["signed_by"] == "lead@client"
    assert rec["source"]["workbook"] == "brownfield-review-2026"
    # the signed object leaves the backlog; the two still unexamined stay in it
    assert len(body["backlog"]["unexplained"]) == 2
    assert keys[0] not in [d["key"] for d in body["backlog"]["drafts"]]


def test_signing_an_unknown_draft_is_a_404():
    eid = _eng()
    _dig(eid)
    r = c.post(f"/engagements/{eid}/insight/archaeology/sign", json={"keys": ["nope:nope:nope"]})
    assert r.status_code == 404


def test_debt_publishes_what_it_did_not_measure():
    eid = _eng()
    _dig(eid)
    debt = c.get(f"/engagements/{eid}/insight/archaeology").json()["debt"]
    assert debt["counts"]["undocumented_customisation"] == 3
    assert debt["score"] == 18 and debt["top_driver"] == "undocumented_customisation"
    assert "custom_object" in debt["unmeasured"]


def test_timetravel_replays_the_ledger_to_a_moment():
    eid = _eng()
    _dig(eid)
    entries = c.get(f"/engagements/{eid}/ledger").json()["entries"]
    early, late = entries[0]["ts"], entries[-1]["ts"]
    assert c.get(f"/engagements/{eid}/insight/timetravel", params={"at": early}).json()["entries"] == \
        sum(1 for e in entries if e["ts"] <= early)
    assert c.get(f"/engagements/{eid}/insight/timetravel",
                 params={"at": late}).json()["entries"] == len(entries)


def test_blast_radius_counts_people_from_the_live_system():
    eid = _eng()
    body = c.post(f"/engagements/{eid}/insight/blast", json={
        "system_id": SYSTEM, "entity": "FOCostCenter", "id_field": "externalCode",
        "selector": {"cust_region": "EMEA"}, "delta": "region rollup corrected"}).json()
    assert body["population"] == 3 and body["affected"] == 2
    assert "region rollup corrected" in body["statement"]


def test_blast_refuses_when_no_row_carries_the_identifying_field():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/insight/blast", json={
        "system_id": SYSTEM, "entity": "FOCostCenter", "id_field": "userId", "selector": {}})
    assert r.status_code == 422 and "cannot be named" in r.json()["detail"]


def test_the_backlog_document_projects_the_drafts():
    eid = _eng()
    _dig(eid)
    assert any(d["id"] == "archaeology-backlog"
               for d in c.get(f"/engagements/{eid}/documents").json()["documents"])
    doc = c.get(f"/engagements/{eid}/documents/archaeology-backlog").text
    assert "3 object(s) recovered" in doc and "unexplained" in doc
    assert "Score 18" in doc


def test_recovered_and_signed_objects_are_planned_documented_and_verified():
    """The whole point: after signing, nothing downstream knows this came from archaeology.

    The record is planned by the planner, printed by the configuration rationale, and checked by
    a verification run — and because it was read out of the live system moments earlier, the
    verification matches. Brownfield becomes an ordinary engagement.
    """
    eid = _eng(role="TARGET", connectivity={"write_credentials": "vault:sf"})
    keys = [d["key"] for d in _dig(eid).json()["drafts"]]
    c.post(f"/engagements/{eid}/insight/archaeology/sign",
           json={"keys": keys, "workbook": "brownfield-review"}, headers=hdr("lead@client", "builder"))

    plan = c.post(f"/engagements/{eid}/plan").json()
    assert len(plan["steps"]) == len(keys)

    rationale = c.get(f"/engagements/{eid}/documents/config-rationale").text
    assert "lead@client" in rationale and "CC-1000" in rationale

    verified = c.post(f"/engagements/{eid}/verification").json()
    assert len(verified["verified"]) == len(keys)
    assert verified["drift"] == [] and verified["planning_blocked"] is False
