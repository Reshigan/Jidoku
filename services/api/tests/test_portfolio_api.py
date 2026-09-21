"""Every engagement at once, worst first — and every number the same one its own screen shows."""
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


def _eng(name):
    eid = c.post("/engagements", json={"name": name, "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    return eid


def _mine(out, eid):
    return next(r for r in out["engagements"] if r["engagement_id"] == eid)


def test_a_broken_chain_outranks_everything_else_on_the_list():
    """A row that says three things says none of them, and nothing an engagement claims is
    provable while its chain does not verify."""
    quiet = _eng("quiet programme")
    broken = _eng("tampered programme")
    STORE.get(broken).ledger.entries[0]["detail"] = "tampered after the fact"
    out = c.get("/portfolio").json()
    ids = [r["engagement_id"] for r in out["engagements"]]
    assert ids.index(broken) < ids.index(quiet)
    assert "does not verify" in _mine(out, broken)["needs_a_person"]
    assert _mine(out, broken)["chain_ok"] is False


def test_a_statutory_block_is_named_as_the_thing_jidoka_will_not_invent():
    eid = _eng("payroll")
    c.post(f"/engagements/{eid}/decisions",
           json={"dp_id": "DP-TAX", "dp_type": "STATUTORY", "question": "UIF ceiling?",
                 "owner": "the client"})
    row = _mine(c.get("/portfolio").json(), eid)
    assert row["statutory_open"] == ["DP-TAX"]
    assert "will not invent" in row["needs_a_person"]


def test_an_engagement_with_nothing_wrong_asks_for_nothing():
    eid = _eng("clean programme")
    c.post(f"/engagements/{eid}/nightshift")
    row = _mine(c.get("/portfolio").json(), eid)
    assert row["needs_a_person"] == "" and row["night_running"] is True


def test_a_night_that_has_never_run_is_on_the_list_rather_than_assumed_fine():
    """The failure this exists for: a programme nobody has looked at in three weeks looks
    identical to one that is going well."""
    eid = _eng("forgotten programme")
    row = _mine(c.get("/portfolio").json(), eid)
    assert row["night_running"] is False and row["needs_a_person"]


def test_the_roll_up_and_the_engagement_screen_agree_on_the_numbers():
    """A roll-up that computed anything differently would be a second opinion, and the first
    argument in every steering meeting would be about which one is right."""
    eid = _eng("payroll")
    c.post(f"/engagements/{eid}/nightshift")
    row = _mine(c.get("/portfolio").json(), eid)
    assert row["proven"] == c.get(f"/engagements/{eid}/verification/assurance").json()["fraction"]
    assert row["night_says"] == c.get(f"/engagements/{eid}/nightshift").json()["clock"]["says"]


def test_it_is_readable_without_a_privileged_role():
    """A roll-up only the most senior person can open gets screenshotted into a slide once a
    month and is wrong by the meeting."""
    assert c.get("/portfolio", headers=hdr("an.auditor", "auditor")).status_code == 200
