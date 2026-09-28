"""The tier is the adapter's to declare, never the workbook's to assert.

Found by compiling a real client design pack: the profile wrote tier A for picklist options, the
SuccessFactors adapter declares them tier B, nothing cross-checked, and the planner produced 198
`API_WRITE` steps against objects SAP publishes no write API for. Two of this repository's own
fixtures had the same lie in them.
"""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.main import app

c = TestClient(app)
SIGNED = {"workbook": "w.xlsx", "signed_by": "T. Mabaso", "date": "2026-09-01"}


def rec(object_, tier, code="X1", product="SuccessFactors"):
    return {"object": object_, "product": product, "system_binding": "S1", "tier": tier,
            "external_code": code, "intent": {"externalCode": code}, "source": dict(SIGNED)}


def _eng():
    return c.post("/engagements", json={"name": "Tiers", "client": "Komatsu"}).json()["engagement_id"]


def test_a_workbook_that_overstates_the_tier_is_refused_with_both_answers_named():
    """PicklistOption is tier B in the adapter. A plan built on the workbook's answer would
    rehearse an API call against something only a person can change."""
    r = c.post(f"/engagements/{_eng()}/ir", json=[rec("PicklistOption", "A")])
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert "the workbook says tier A" in detail and "declares 'PicklistOption' as tier B" in detail
    assert "The product decides what it publishes a write path for" in detail


def test_the_adapters_own_answer_loads():
    assert c.post(f"/engagements/{_eng()}/ir",
                  json=[rec("PicklistOption", "B")]).status_code == 200
    assert c.post(f"/engagements/{_eng()}/ir",
                  json=[rec("FOCompany", "A", code="KOM01")]).status_code == 200


def test_understating_the_tier_is_refused_too():
    """A tier-C instruction sheet for an object with a real write API is not "safe" — it hands a
    person work the platform could have rehearsed, and the evidence says a human did it."""
    r = c.post(f"/engagements/{_eng()}/ir", json=[rec("FOCompany", "C", code="KOM01")])
    assert r.status_code == 422 and "declares 'FOCompany' as tier A" in r.json()["detail"]


def test_an_object_no_adapter_knows_may_be_tier_b_or_c_but_never_tier_a():
    """A person doing it by hand needs no entry in a map. What cannot be claimed is a write path
    nothing can name."""
    eid = _eng()
    assert c.post(f"/engagements/{eid}/ir",
                  json=[rec("cust_SomethingNew", "C")]).status_code == 200
    r = c.post(f"/engagements/{eid}/ir", json=[rec("cust_SomethingNew", "A")])
    assert r.status_code == 422 and "nothing can name the write path" in r.json()["detail"]


def test_the_refusal_comes_at_load_because_the_earlier_refusal_is_the_kinder_one():
    """This was caught at execute time, after the design had been loaded, planned, and put in
    front of an operator with an armed target."""
    eid = _eng()
    assert c.post(f"/engagements/{eid}/ir", json=[rec("PicklistOption", "A")]).status_code == 422
    assert c.get(f"/engagements/{eid}/ir").json()["records"] == [], "nothing was kept"
