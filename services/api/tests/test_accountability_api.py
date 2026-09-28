"""The platform's account of itself: a refusal is on the chain, and so is what happened next.

The gates were the product and they left no trace. A plan blocked on an open statutory decision,
an approval refused because the reviewer was the builder — each returned a 403, the operator read
it, and it was gone. So the one question a customer eventually asks about a governance platform
had no answer in it: are these gates right, or are they friction?
"""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


def _eng():
    return c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]


def test_a_refusal_is_recorded_against_the_person_it_refused():
    eid = _eng()
    r = c.post(f"/engagements/{eid}/people", json=[{"name": "A. Silva", "authority": ["approve"]}],
               headers=hdr("an.auditor", "auditor"))
    assert r.status_code == 403
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "REFUSED")
    assert entry["actor"] == "an.auditor" and entry["status"] == 403
    assert "people" in entry["task"] and entry["task"].startswith("POST ")
    assert "may not 'register_system'" in entry["detail"]


def test_the_gate_is_named_by_route_not_by_url():
    """Without the template each engagement's refusals would be their own row, and a pattern
    across a portfolio would be invisible."""
    eid = _eng()
    c.post(f"/engagements/{eid}/people", json=[], headers=hdr("an.auditor", "auditor"))
    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "REFUSED")
    assert eid not in entry["task"] and "{eid}" in entry["task"]


def test_a_gate_that_holds_and_a_gate_that_is_cleared_read_differently():
    eid = _eng()
    led = STORE.get(eid).ledger
    c.post(f"/engagements/{eid}/people", json=[{"name": "A", "authority": ["approve"]}],
           headers=hdr("a.builder", "auditor"))          # refused: no register_system
    assert any(e["action"] == "REFUSED" for e in led.entries)

    out = c.get(f"/engagements/{eid}/accountability").json()
    gate = out["refusals"]["gates"][0]
    assert gate["fired"] == 1 and gate["standing"] == 1 and gate["cleared"] == 0
    assert "stopping something nobody has resolved" in gate["reads_as"]

    # The same person, past the same gate, later — which is the only thing that counts as cleared.
    c.post(f"/engagements/{eid}/people", json=[{"name": "A", "authority": ["approve"]}],
           headers=hdr("a.builder", "builder"))
    assert any(e["action"] == "CLEARED" for e in led.entries)
    out = c.get(f"/engagements/{eid}/accountability").json()
    assert out["refusals"]["cleared"] == 1 and out["refusals"]["still_standing"] == 0


def test_somebody_else_succeeding_is_separation_of_duties_not_a_clearing():
    eid = _eng()
    c.post(f"/engagements/{eid}/people", json=[{"name": "A", "authority": ["approve"]}],
           headers=hdr("an.auditor", "auditor"))
    c.post(f"/engagements/{eid}/people", json=[{"name": "A", "authority": ["approve"]}],
           headers=hdr("a.builder", "builder"))
    out = c.get(f"/engagements/{eid}/accountability").json()
    assert out["refusals"]["still_standing"] == 1, \
        "another person getting through is the gate working, not this person's refusal clearing"


def test_it_publishes_what_it_cannot_measure():
    """The gap between what a metric covers and what a reader assumes it covers is where every
    dishonest dashboard lives."""
    out = c.get(f"/engagements/{_eng()}/accountability").json()
    assert any("never reached a gate" in u for u in out["unmeasurable"])
    assert any("Harm avoided" in u for u in out["unmeasurable"])
    assert "twin has not made enough settled predictions" in out["says"]


def test_a_record_it_called_verified_and_then_found_wrong_is_counted_apart():
    """Drift in general is the system changing. Drift on something already verified is the
    platform having been wrong with confidence."""
    eid = _eng()
    led = STORE.get(eid).ledger
    led.append("SF:PICKLIST:A", "VERIFIED", "jidoka", "read back and matched")
    led.append("SF:PICKLIST:A", "DRIFT_DETECTED", "jidoka", "the system says something else")
    led.append("SF:PICKLIST:B", "DRIFT_DETECTED", "jidoka", "never verified, just different")
    out = c.get(f"/engagements/{eid}/accountability").json()
    assert out["mistakes"]["drift_after_verified"] == ["SF:PICKLIST:A"]
    assert "I called 1 record(s) verified and later found the system disagreeing" in out["says"]
