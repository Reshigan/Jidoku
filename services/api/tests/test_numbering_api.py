"""Number ranges over HTTP: codes as governed allocations, collisions refused with a name."""
from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app

c = TestClient(app)


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    return c.post("/engagements", json={"name": "Numbers", "client": "K"}).json()["engagement_id"]


def _range(eid, **over):
    body = {"range_id": "R1", "object_type": "CostCenter", "prefix": "CC-ZA-",
            "start": 1, "end": 50, "width": 4}
    body.update(over)
    return c.post(f"/engagements/{eid}/numbering/ranges", json=body)


def test_register_allocate_and_snapshot():
    eid = _eng()
    assert _range(eid).status_code == 200
    r = c.post(f"/engagements/{eid}/numbering/allocate", json={"object_type": "CostCenter"})
    assert r.json()["allocated"] == "CC-ZA-0001"
    snap = c.get(f"/engagements/{eid}/numbering").json()
    assert list(snap["allocated"]) == ["CC-ZA-0001"]
    assert snap["ranges"][0]["next_free"] == "CC-ZA-0002"


def test_a_collision_is_409_and_names_the_holder():
    eid = _eng()
    _range(eid)
    c.post(f"/engagements/{eid}/numbering/allocate",
           json={"object_type": "CostCenter", "code": "CC-ZA-0007"}, headers=hdr("amara", "builder"))
    r = c.post(f"/engagements/{eid}/numbering/allocate",
               json={"object_type": "CostCenter", "code": "CC-ZA-0007"}, headers=hdr("ben", "builder"))
    assert r.status_code == 409 and "amara" in r.json()["detail"]


def test_an_overlapping_range_is_refused_with_422():
    eid = _eng()
    _range(eid)
    assert _range(eid, range_id="R2", start=40, end=90).status_code == 422


def test_ir_load_refuses_a_code_outside_its_governed_range():
    eid = _eng()
    _range(eid, object_type="TimeType", prefix="TT-", start=1, end=9)
    rec = {"object": "TimeType", "product": "SuccessFactors", "system_binding": "S1", "tier": "A",
           "external_code": "ROGUE-99", "intent": {"externalCode": "ROGUE-99"},
           "source": {"workbook": "WB", "signed_by": "x", "date": "2026-09-01"}}
    r = c.post(f"/engagements/{eid}/ir", json=[rec])
    assert r.status_code == 422
    assert c.get(f"/engagements/{eid}/ir").json()["records"] == []


def test_ir_load_accepts_a_code_inside_its_governed_range():
    eid = _eng()
    _range(eid, object_type="TimeType", prefix="TT-", start=1, end=9, width=2)
    rec = {"object": "TimeType", "product": "SuccessFactors", "system_binding": "S1", "tier": "A",
           "external_code": "TT-03", "intent": {"externalCode": "TT-03"},
           "source": {"workbook": "WB", "signed_by": "x", "date": "2026-09-01"}}
    assert c.post(f"/engagements/{eid}/ir", json=[rec]).status_code == 200


def test_ungoverned_object_types_load_as_before():
    eid = _eng()
    _range(eid, object_type="TimeType", prefix="TT-", start=1, end=9)
    rec = {"object": "LegalEntity", "product": "SuccessFactors", "system_binding": "S1", "tier": "A",
           "external_code": "ZA01", "intent": {"externalCode": "ZA01"},
           "source": {"workbook": "WB", "signed_by": "x", "date": "2026-09-01"}}
    assert c.post(f"/engagements/{eid}/ir", json=[rec]).status_code == 200
