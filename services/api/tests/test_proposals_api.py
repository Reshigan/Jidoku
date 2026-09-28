"""An agent drafts; a person signs; the record then meets the same gates as any other.

What these pin is the separation, because that is the invariant: the drafter cannot sign, the signer
cannot be the drafter, the signature comes from the authenticated identity and never from the body,
and signing one record must not delete the rest of the design.
"""
from fastapi.testclient import TestClient
from jidoka_api.auth import issue_token
from jidoka_api.main import app
from jidoka_api.routers.engagements import STORE

c = TestClient(app)


def draft(code="CC1", **over):
    rec = {"object": "FOCostCenter", "product": "SuccessFactors", "system_binding": "KOM-SF-DEV",
           "tier": "A", "external_code": code,
           "intent": {"externalCode": code, "name": f"Cost centre {code}"},
           "source": {"workbook": "SDD §5.1", "signed_by": "", "date": ""}}
    return {**rec, **over}


def hdr(subject, *roles):
    return {"Authorization": f"Bearer {issue_token(subject, roles)}"}


AGENT = hdr("k5.agent", "builder")
APPROVER = hdr("n.sango", "approver")


def _eng():
    return c.post("/engagements", json={"name": "ZA", "client": "Komatsu"}).json()["engagement_id"]


def _propose(eid, *records, who=AGENT):
    return c.post(f"/engagements/{eid}/proposals", json={"records": list(records)}, headers=who)


def test_a_draft_is_recorded_and_says_it_is_not_intent_yet():
    eid = _eng()
    r = _propose(eid, draft())
    assert r.status_code == 200
    assert r.json()["proposed"] == ["SuccessFactors:FOCostCenter:CC1"]
    assert "None is intent until a person signs it" in r.json()["says"]
    assert STORE.get(eid).ir == []                       # nothing was loaded


def test_a_draft_that_arrives_carrying_a_signature_is_refused():
    eid = _eng()
    forged = draft(source={"workbook": "SDD", "signed_by": "N. Sango", "date": "2026-09-30"})
    r = _propose(eid, forged)
    assert r.status_code == 422 and "asserting an approval nobody gave" in r.json()["detail"]
    assert c.get(f"/engagements/{eid}/proposals", headers=AGENT).json()["proposals"] == []


def test_a_batch_is_checked_whole_so_a_half_refused_pass_leaves_nothing_to_read():
    eid = _eng()
    r = _propose(eid, draft("CC1"), draft("CC2", tier="C"))       # the adapter says FOCostCenter is A
    assert r.status_code == 422 and "record 1" in r.json()["detail"]
    assert c.get(f"/engagements/{eid}/proposals", headers=AGENT).json()["proposals"] == []


def test_a_draft_claiming_a_tier_the_adapter_denies_is_refused_at_intake_not_at_signing():
    eid = _eng()
    r = _propose(eid, draft(object="PicklistOption", tier="A"))
    assert r.status_code == 422 and "adapter declares" in r.json()["detail"]


def test_the_drafter_cannot_sign_because_signing_needs_approve_and_a_builder_has_none():
    eid = _eng()
    _propose(eid, draft())
    r = c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=AGENT)
    assert r.status_code == 403


def test_a_person_with_approve_signs_and_the_record_is_loaded_signed_by_them():
    eid = _eng()
    _propose(eid, draft())
    r = c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=APPROVER)
    assert r.status_code == 200 and r.json()["signed_by"] == "n.sango"
    loaded = STORE.get(eid).ir
    assert [rec.key for rec in loaded] == ["SuccessFactors:FOCostCenter:CC1"]
    # Stamped from the authenticated identity — there was no field in the request to put a name in.
    assert loaded[0].source["signed_by"] == "n.sango" and loaded[0].source["date"]
    assert loaded[0].source["workbook"] == "SDD §5.1"


def test_whoever_drafted_a_record_may_not_be_the_one_who_signs_it():
    eid = _eng()
    both = hdr("one.person", "builder", "approver")
    _propose(eid, draft(), who=both)
    r = c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=both)
    assert r.status_code == 409 and "may not sign it" in r.json()["detail"]
    assert STORE.get(eid).ir == []


def test_signing_one_record_keeps_the_rest_of_the_design_it_merges_and_never_replaces():
    eid = _eng()
    _propose(eid, draft("CC1"), draft("CC2"))
    c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=APPROVER)
    c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC2/sign", headers=APPROVER)
    assert sorted(r.key for r in STORE.get(eid).ir) == ["SuccessFactors:FOCostCenter:CC1", "SuccessFactors:FOCostCenter:CC2"]


def test_the_signed_record_meets_the_same_gates_as_a_workbook_upload():
    # An orphaned tier lie can reach the store only if a second load path is weaker than the first.
    # Here the record is valid at intake and the store is then edited underneath — the shared
    # load path still refuses what it would refuse from a workbook.
    eid = _eng()
    _propose(eid, draft("CC1"))
    STORE.get(eid).numbering.validate = lambda *_a, **_k: "code CC1 is outside the agreed range"
    r = c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=APPROVER)
    assert r.status_code == 422 and "outside the agreed range" in r.json()["detail"]


def test_a_rejection_needs_a_reason_and_leaves_the_draft_unloaded():
    eid = _eng()
    _propose(eid, draft())
    no_reason = c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/reject",
                       json={"reason": " "}, headers=APPROVER)
    assert no_reason.status_code == 422
    ok = c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/reject",
                json={"reason": "wrong cost centre group"}, headers=APPROVER)
    assert ok.status_code == 200 and STORE.get(eid).ir == []
    row = c.get(f"/engagements/{eid}/proposals", headers=AGENT).json()["proposals"][0]
    assert row["status"] == "rejected" and row["reason"] == "wrong cost centre group"


def test_a_resolved_proposal_cannot_be_signed_or_rejected_again():
    eid = _eng()
    _propose(eid, draft())
    c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=APPROVER)
    assert c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign",
                  headers=hdr("other.approver", "approver")).status_code == 409
    assert c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/reject", json={"reason": "x"},
                  headers=APPROVER).status_code == 409


def test_a_proposal_nobody_made_is_a_404_not_an_empty_success():
    eid = _eng()
    assert c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:NOPE/sign",
                  headers=APPROVER).status_code == 404


def test_the_listing_counts_by_state_and_needs_only_read():
    eid = _eng()
    _propose(eid, draft("CC1"), draft("CC2"))
    c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=APPROVER)
    out = c.get(f"/engagements/{eid}/proposals", headers=hdr("an.auditor", "auditor")).json()
    assert (out["pending"], out["signed"], out["rejected"]) == (1, 1, 0)


def test_the_chain_records_who_proposed_and_who_signed_so_the_separation_can_be_audited():
    eid = _eng()
    _propose(eid, draft())
    c.post(f"/engagements/{eid}/proposals/SuccessFactors:FOCostCenter:CC1/sign", headers=APPROVER)
    acts = {e["action"]: e["actor"] for e in STORE.get(eid).ledger.entries
            if e["action"] in ("IR_PROPOSED", "IR_SIGNED")}
    assert acts == {"IR_PROPOSED": "k5.agent", "IR_SIGNED": "n.sango"}
