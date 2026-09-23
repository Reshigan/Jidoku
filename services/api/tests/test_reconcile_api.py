"""Over HTTP: consuming the product's own audit trail instead of competing with it."""
import json
import pathlib

from fastapi.testclient import TestClient
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)
IR = json.load(open(pathlib.Path(__file__).parents[3] /
                    "packages/jidoka-core/tests/fixtures/komatsu_sample_ir.json"))
SYSTEM = IR[0]["system_binding"]


def _eng(bind=True):
    eid = c.post("/engagements", json={"name": "ZA payroll", "client": "Komatsu"}).json()["engagement_id"]
    c.post(f"/engagements/{eid}/ir", json=IR)
    c.post(f"/engagements/{eid}/systems", json={
        "system_id": SYSTEM, "product": "SuccessFactors", "role": "TARGET", "environment": "DEV",
        "connectivity": {"write_credentials": "vault:sf"}})
    if bind:
        c.post(f"/engagements/{eid}/execution/connector", json={"system_id": SYSTEM, "kind": "mock"})
    return eid


def _seed_log(eid, rows):
    """The tenant's own Change Audit, as the mock would serve it."""
    STORE.get(eid).connectors[SYSTEM].mock.collections["ChangeAudit"] = rows


def test_an_unreadable_change_log_is_a_refusal_not_a_clean_bill_of_health():
    """A reconciliation that found nothing and one that could not look produce the same number
    and mean opposite things."""
    eid = _eng(bind=False)
    r = c.post(f"/engagements/{eid}/reconcile?system_id={SYSTEM}")
    assert r.status_code == 409
    assert "different thing from no change having been made" in r.json()["detail"]


def test_a_change_nobody_made_through_the_platform_is_found_and_ledgered():
    eid = _eng()
    key = STORE.get(eid).ir[0].key
    _seed_log(eid, [{"objectId": key, "modifiedBy": "n.consultant",
                     "modifiedDate": "2026-09-22T14:00:00Z", "changeType": "UPDATE"}])

    out = c.post(f"/engagements/{eid}/reconcile?system_id={SYSTEM}").json()
    assert len(out["out_of_band"]) == 1 and out["out_of_band"][0]["by"] == "n.consultant"

    entry = next(e for e in STORE.get(eid).ledger.entries if e["action"] == "OUT_OF_BAND")
    assert entry["changed_by"] == "n.consultant" and entry["task"] == key


def test_an_engagement_nobody_reconciled_says_so_rather_than_reporting_clean():
    """Every number here assumes nothing was done outside the platform, and that is an
    assumption rather than a finding until somebody looks."""
    eid = _eng()
    out = c.get(f"/engagements/{eid}/reconcile").json()
    assert out["ever_run"] is False and "an assumption, not a finding" in out["says"]


def test_the_result_survives_a_restart_because_it_is_read_off_the_chain():
    eid = _eng()
    key = STORE.get(eid).ir[0].key
    _seed_log(eid, [{"objectId": key, "modifiedBy": "n.consultant",
                     "modifiedDate": "2026-09-22T14:00:00Z"}])
    c.post(f"/engagements/{eid}/reconcile?system_id={SYSTEM}")

    out = c.get(f"/engagements/{eid}/reconcile").json()
    assert out["ever_run"] is True and len(out["out_of_band"]) == 1
    assert "outside the platform" in out["says"]


def test_the_products_field_names_are_translated_by_the_adapter_not_the_reconciler():
    """Every product spells its log differently, and the translation belongs with the product."""
    eid = _eng()
    key = STORE.get(eid).ir[0].key
    _seed_log(eid, [{"entityName": key, "changedBy": "someone", "changedOn": "2026-09-22T10:00:00Z"}])
    out = c.post(f"/engagements/{eid}/reconcile?system_id={SYSTEM}").json()
    assert out["out_of_band"] and out["out_of_band"][0]["by"] == "someone"


def test_the_night_shift_wakes_somebody_for_a_change_made_outside_the_platform():
    """Above a half-landed write: a partial is a state nobody designed and everybody can see,
    and this is a change nobody knew about at all."""
    eid = _eng()
    key = STORE.get(eid).ir[0].key
    _seed_log(eid, [{"objectId": key, "modifiedBy": "n.consultant",
                     "modifiedDate": "2026-09-22T14:00:00Z"}])
    c.post(f"/engagements/{eid}/reconcile?system_id={SYSTEM}")

    night = c.post(f"/engagements/{eid}/nightshift").json()
    rows = night["interrupted"] + night["waited"] + night["deferred"]
    found = next(f for f in rows if f["kind"] == "out_of_band")
    assert found["cost"] == 95 and key in found["what"]
    assert found in night["interrupted"], "this is worth waking somebody for"


def test_the_account_of_itself_no_longer_calls_this_unmeasurable():
    """A stale limit is worse than none, because it is the one that gets quoted."""
    eid = _eng()
    out = c.get(f"/engagements/{eid}/accountability").json()
    text = " ".join(out["unmeasurable"])
    assert "whose own change log nothing has read" in text
    assert "is found and counted" in text
