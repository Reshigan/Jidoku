"""M6: stated once, overridden by a name, revisited where the consequence lands.

Not to be right — because the loop closing is what makes the next objection worth hearing.
"""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE
from jidoka_api.routers.objections import raise_once
from jidoka_core.objections import Objection

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))
OBJ = {"about": "SF:PICKLIST:A", "finding": "rests on an attestation, not a check",
       "grounds": "unevidenced",
       "consequence": "if the person is mistaken nobody finds out until payroll runs",
       "recommendation": "build a read path before cutover"}


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    return c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]


def _raise(eid, **over):
    """The platform raises its own objections — there is no endpoint for it and no button, because
    M6 is about JIDOKA's position. A person who disagrees raises a decision point."""
    return raise_once(STORE.get(eid), Objection(**{**OBJ, **over}), "jidoka.auditor")


def test_there_is_no_way_for_a_person_to_raise_one_on_the_platforms_behalf():
    """A human's objection is a decision point. This is the platform's own position, and a route
    that let somebody else state it would make the record meaningless."""
    assert c.post(f"/engagements/{_eng()}/objections", json=OBJ).status_code in (404, 405)


def test_it_is_stated_once():
    """A tool that repeats itself is a tool people configure to be quiet, and then the one
    objection that mattered is quiet too."""
    eid = _eng()
    first = _raise(eid)
    second = _raise(eid)
    assert first["objection_id"] == second["objection_id"]
    assert first["already_open"] is False and second["already_open"] is True
    out = c.get(f"/engagements/{eid}/objections").json()
    assert len(out["objections"]) == 1 and out["objections"][0]["restated"] == 1


def test_an_override_carries_a_persons_name_and_their_reason():
    """An override nobody signed is the platform being overruled by the weather."""
    eid = _eng()
    oid = _raise(eid)["objection_id"]
    bad = c.post(f"/engagements/{eid}/objections/{oid}/override",
                 json={"decided_by": "", "reason": "ship it"}, headers=hdr("an.approver", "approver"))
    assert bad.status_code == 422
    ok = c.post(f"/engagements/{eid}/objections/{oid}/override",
                json={"decided_by": "T. Mabaso", "reason": "the vendor confirmed it in writing"},
                headers=hdr("an.approver", "approver"))
    assert ok.status_code == 200 and ok.json()["decided_by"] == "T. Mabaso"
    row = c.get(f"/engagements/{eid}/objections").json()["objections"][0]
    assert row["status"] == "overridden" and row["overridden_by"] == "T. Mabaso"


def test_the_platform_never_overrides_its_own_objection():
    """Overruling the platform's stated position is a decision, and the platform is never the one
    who makes it (invariant 7)."""
    eid = _eng()
    oid = _raise(eid)["objection_id"]
    r = c.post(f"/engagements/{eid}/objections/{oid}/override",
               json={"decided_by": "T. Mabaso", "reason": "ship it"},
               headers=hdr("a.builder", "builder"))
    assert r.status_code == 403 and "may not 'approve'" in r.json()["detail"]


def test_nothing_is_due_before_the_consequence_could_have_landed():
    """A revisit early is a platform asking to be told it was right."""
    eid = _eng()
    oid = _raise(eid)["objection_id"]
    c.post(f"/engagements/{eid}/objections/{oid}/override",
           json={"decided_by": "T. Mabaso", "reason": "ship it"}, headers=hdr("a", "approver"))
    out = c.get(f"/engagements/{eid}/objections").json()
    assert out["phase"] == "DISCOVER" and out["due_for_revisit"] == []

    STORE.get(eid).phase = "HYPERCARE"
    out = c.get(f"/engagements/{eid}/objections").json()
    assert [o["objection_id"] for o in out["due_for_revisit"]] == [oid]


def test_the_revisit_reports_what_the_chain_says_not_who_was_right():
    """"The objection was right" is a claim about a world where the override did not happen, and
    nothing here can see that world."""
    eid = _eng()
    oid = _raise(eid)["objection_id"]
    c.post(f"/engagements/{eid}/objections/{oid}/override",
           json={"decided_by": "T. Mabaso", "reason": "ship it"}, headers=hdr("a", "approver"))
    STORE.get(eid).ledger.append("SF:PICKLIST:A", "DRIFT_DETECTED", "jidoka", "it disagrees")

    out = c.post(f"/engagements/{eid}/objections/{oid}/revisit").json()
    assert "the live system has since disagreed" in out["says"]
    assert out["overridden_by"] == "T. Mabaso"
    assert "right" not in out["says"] and "vindicat" not in out["says"]
    assert c.get(f"/engagements/{eid}/objections").json()["objections"][0]["status"] == "revisited"


def test_silence_is_not_read_as_agreement():
    eid = _eng()
    oid = _raise(eid)["objection_id"]
    c.post(f"/engagements/{eid}/objections/{oid}/override",
           json={"decided_by": "T. Mabaso", "reason": "ship it"}, headers=hdr("a", "approver"))
    out = c.post(f"/engagements/{eid}/objections/{oid}/revisit").json()
    assert "not the same as nothing having happened" in out["says"]


def test_only_something_somebody_set_aside_has_a_consequence_to_come_back_to():
    eid = _eng()
    oid = _raise(eid)["objection_id"]
    r = c.post(f"/engagements/{eid}/objections/{oid}/revisit")
    assert r.status_code == 409 and "somebody set aside" in r.json()["detail"]


def test_the_night_shift_is_where_the_loop_closes():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    oid = _raise(eid)["objection_id"]
    c.post(f"/engagements/{eid}/objections/{oid}/override",
           json={"decided_by": "T. Mabaso", "reason": "ship it"}, headers=hdr("a", "approver"))
    STORE.get(eid).phase = "HYPERCARE"
    night = c.post(f"/engagements/{eid}/nightshift").json()
    rows = night["interrupted"] + night["waited"] + night["deferred"]
    found = next(f for f in rows if f["kind"] == "objection_due")
    assert oid in found["what"] and "T. Mabaso" in found["detail"]
    assert "if the person is mistaken" in found["detail"], "it repeats what it predicted"


def test_the_crew_writes_down_what_the_ring_that_cannot_write_said():
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    c.post(f"/engagements/{eid}/run")
    out = c.get(f"/engagements/{eid}/objections").json()
    assert out["objections"], "the auditor objected and nothing recorded it"
    assert all(o["consequence"] and o["recommendation"] for o in out["objections"])
    assert all(o["status"] == "open" for o in out["objections"])


def test_the_platform_concedes_on_its_own_evidence_not_on_a_button():
    """The objector re-states everything it still finds, so an objection left open that it did not
    restate no longer holds. Without a way to concede, the only exits were being overruled or
    being right — and a platform nobody can argue with honestly is one nobody argues with."""
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    stale = _raise(eid, about="SF:GONE", finding="a finding that no longer holds")
    out = c.post(f"/engagements/{eid}/run").json()
    assert stale["objection_id"] in out["objections_withdrawn"]
    rows = {o["objection_id"]: o for o in c.get(f"/engagements/{eid}/objections").json()["objections"]}
    assert rows[stale["objection_id"]]["status"] == "withdrawn"
    assert any(o["status"] == "open" for o in rows.values()), "what it still finds stays open"


def test_conceding_does_not_touch_one_somebody_already_set_aside():
    """An override is a person's decision, and a later run is not entitled to quietly undo it."""
    eid = _eng()
    c.post(f"/engagements/{eid}/ir", json=IR)
    oid = _raise(eid, about="SF:GONE", finding="a finding that no longer holds")["objection_id"]
    c.post(f"/engagements/{eid}/objections/{oid}/override",
           json={"decided_by": "T. Mabaso", "reason": "ship it"}, headers=hdr("a", "approver"))
    out = c.post(f"/engagements/{eid}/run").json()
    assert oid not in out["objections_withdrawn"]
    rows = {o["objection_id"]: o for o in c.get(f"/engagements/{eid}/objections").json()["objections"]}
    assert rows[oid]["status"] == "overridden"
