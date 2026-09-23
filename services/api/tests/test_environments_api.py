"""The cutover question over HTTP: read both, compare, write nothing."""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.main import app

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))
QA, PROD = "KOM-SF-QA", "KOM-SF-PROD"


def _register(eid, system_id, role="TEST", product="SuccessFactors"):
    return c.post(f"/engagements/{eid}/systems", json={
        "system_id": system_id, "product": product, "role": role, "environment": role,
        "connectivity": {"write_credentials": "vault:sf"} if role not in ("SOURCE_LEGACY", "TWIN") else {}})


def _eng(bind=(QA, PROD)):
    eid = c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    for s in (QA, PROD):
        _register(eid, s)
    # A reader, not a writer: a comparison only reads, and the systems worth comparing are
    # usually ones no IR record binds to — the design names DEV and the question is about PROD.
    for s in bind:
        c.post(f"/engagements/{eid}/execution/connector/reader",
               json={"system_id": s, "kind": "mock"})
    return eid


def test_two_mocks_of_the_same_product_line_up():
    eid = _eng()
    out = c.get(f"/engagements/{eid}/environments/compare?left={QA}&right={PROD}").json()
    assert out["aligned"] is True and "agree on all" in out["says"]
    assert "not a verdict on either" not in out["says"]


def test_a_system_with_nothing_connected_is_a_refusal_not_an_empty_answer():
    """An empty diff would read as "these two agree", which is a different fact from "nothing was
    read"."""
    eid = _eng(bind=(QA,))
    r = c.get(f"/engagements/{eid}/environments/compare?left={QA}&right={PROD}")
    assert r.status_code == 409 and "the binding it wants is a reader" in r.json()["detail"]


def test_two_products_are_refused_rather_than_diffed_into_nonsense():
    eid = _eng()
    _register(eid, "KOM-S4-DEV", role="DEV", product="S4HANA")
    c.post(f"/engagements/{eid}/execution/connector/reader",
           json={"system_id": "KOM-S4-DEV", "kind": "mock"})
    r = c.get(f"/engagements/{eid}/environments/compare?left={QA}&right=KOM-S4-DEV")
    assert r.status_code == 422 and "do not hold the same objects" in r.json()["detail"]


def test_a_system_the_landscape_does_not_know_is_refused():
    eid = _eng()
    r = c.get(f"/engagements/{eid}/environments/compare?left={QA}&right=WHO-KNOWS")
    assert r.status_code == 422 and "not registered" in r.json()["detail"]


def test_comparing_a_system_with_itself_is_refused_as_useless():
    eid = _eng()
    r = c.get(f"/engagements/{eid}/environments/compare?left={QA}&right={QA}")
    assert r.status_code == 422 and "true and useless" in r.json()["detail"]


def test_a_real_difference_between_two_tenants_is_found_and_named():
    """One tenant carrying a field the other does not is the everyday cutover finding.

    The difference is injected by swapping one system's reader, because a read-only binding is a
    new, smaller object that deliberately does not expose the client it reads through — which is
    the property that makes it read-only, and is worth not working around.
    """
    eid = _eng()
    from jidoka_api.routers.engagements import STORE
    from jidoka_core.registry import SystemRecord  # noqa: F401 — documents where product comes from

    e = STORE.get(eid)
    entity = e.ir[0].object
    reader = e.connectors[PROD]

    def drifted(system, ent):
        rows = [dict(r) for r in reader.fetch(system, ent)]
        if ent == entity and rows:
            rows[0]["cust_toggle"] = "changed in prod only"
        return rows

    e.connectors[PROD] = type(reader)(reader.kind, drifted, reader.apply, reader.describe,
                                      metadata_xml=reader.metadata_xml)

    out = c.get(f"/engagements/{eid}/environments/compare?left={QA}&right={PROD}").json()
    assert out["aligned"] is False and out["apart"] >= 1
    row = next(x for x in out["entities"] if x["entity"] == entity)
    assert row["differs"] and "cust_toggle" in row["differs"][0]["fields"]
    assert "not a verdict on either" in out["says"]


def test_an_entity_the_product_cannot_read_is_listed_rather_than_silently_skipped():
    """A comparison that quietly dropped what it could not read would report alignment it never
    checked."""
    eid = _eng()
    out = c.get(f"/engagements/{eid}/environments/compare?left={QA}&right={PROD}").json()
    assert "unreadable" in out
    for row in out["unreadable"]:
        assert row["reason"], "an entity left out says why"


def test_it_is_a_read_and_needs_nothing_more_than_read():
    eid = _eng()
    from jidoka_api.auth import issue_token

    hdr = {"Authorization": f"Bearer {issue_token('an.auditor', ('auditor',))}"}
    assert c.get(f"/engagements/{eid}/environments/compare?left={QA}&right={PROD}",
                 headers=hdr).status_code == 200
