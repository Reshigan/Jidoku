"""An agent drafts; a person signs. The signature is an act, not a field.

`validate_record` checked that `source.signed_by` was present. That is a check on a field, and a model
can write any name into a field. What is pinned here is that a draft arrives without a signature,
that a drafter who supplies one is refused, and that the only thing which can make a draft loadable
is `sign` — called with an identity, never with text a model produced.
"""
import pytest
from jidoka_core.ir import IRValidationError, validate_record
from jidoka_core.proposals import (PROPOSED, REJECTED, SIGNED, ProposalError, check, draft, sign,
                                   state)

BASE = {"object": "FOPayComponent", "product": "SuccessFactors", "system_binding": "KOM-SF-DEV",
        "tier": "A", "external_code": "BASIC", "intent": {"externalCode": "BASIC", "name": "Basic"},
        "source": {"workbook": "SDD §5.1", "signed_by": "", "date": ""}}


def entry(action, task="FOPayComponent/BASIC", actor="agent", detail="", **extra):
    return {"ts": "2026-09-28T10:00:00Z", "task": task, "action": action, "actor": actor,
            "detail": detail, **extra}


def test_a_draft_with_no_signature_and_a_stated_source_is_clean():
    assert check(BASE) == []


def test_a_drafter_that_writes_a_signature_is_refused_and_told_why():
    signed = {**BASE, "source": {"workbook": "SDD", "signed_by": "N. Sango", "date": "2026-09-30"}}
    problems = check(signed)
    assert len(problems) == 1
    assert "source.signed_by and source.date" in problems[0]
    assert "asserting an approval nobody gave" in problems[0]


def test_a_single_written_field_is_enough_to_refuse():
    just_a_name = {**BASE, "source": {"workbook": "SDD", "signed_by": "N. Sango", "date": ""}}
    assert "source.signed_by" in check(just_a_name)[0]


def test_a_draft_that_cites_nothing_is_refused_because_a_signer_would_have_nothing_to_check_it_against():
    assert any("source.workbook is empty" in p
               for p in check({**BASE, "source": {"workbook": " ", "signed_by": "", "date": ""}}))


def test_the_rest_of_ir_validation_still_runs_over_a_draft():
    broken = {k: v for k, v in BASE.items() if k != "tier"}
    assert any("IR validation" in p for p in check(broken))
    assert any("IR validation" in p for p in check({**BASE, "tier": "Z"}))


def test_a_record_that_is_not_an_object_is_a_problem_not_a_crash():
    assert check("a pay component")[0].startswith("A record is an object")


def test_checking_a_draft_never_mutates_it():
    before = {**BASE, "source": dict(BASE["source"])}
    check(BASE)
    assert BASE == before


def test_a_draft_is_stored_with_provenance_from_what_was_cited_not_from_what_was_typed():
    typed = {**BASE, "source": {"workbook": "something the model made up", "signed_by": "X",
                                "date": "Y"}}
    got = draft(typed, ["SDD §5.1", " DP-C04 ", ""])
    assert got["source"] == {"workbook": "SDD §5.1; DP-C04", "signed_by": "", "date": ""}


def test_an_unsigned_draft_is_unloadable_which_is_invariant_1_holding():
    with pytest.raises(IRValidationError) as ex:
        validate_record(draft(BASE, ["SDD"]))
    assert "does not execute unsigned intent" in str(ex.value)


def test_signing_is_what_makes_a_draft_loadable_and_stamps_the_person_not_a_string_the_model_wrote():
    record, open_dps = validate_record(sign(draft(BASE, ["SDD §5.1"]), "n.sango", "2026-09-30"))
    assert record.source == {"workbook": "SDD §5.1", "signed_by": "n.sango", "date": "2026-09-30"}
    assert open_dps == []


def test_signing_needs_a_person_and_a_date():
    with pytest.raises(ProposalError):
        sign(BASE, " ", "2026-09-30")
    with pytest.raises(ProposalError):
        sign(BASE, "n.sango", "")


def test_signing_returns_a_copy_and_leaves_the_draft_as_drafted():
    d = draft(BASE, ["SDD"])
    sign(d, "n.sango", "2026-09-30")
    assert d["source"]["signed_by"] == ""


def test_state_is_replayed_from_the_chain_and_starts_pending():
    rows = state([entry(PROPOSED, record=BASE, detail="from SDD §5.1")])
    assert rows[0]["status"] == "pending" and rows[0]["proposed_by"] == "agent"
    assert rows[0]["record"]["object"] == "FOPayComponent" and rows[0]["why"] == "from SDD §5.1"


def test_a_signature_and_a_rejection_each_close_a_proposal_and_name_who():
    signed = state([entry(PROPOSED, record=BASE), entry(SIGNED, actor="n.sango")])[0]
    assert signed["status"] == "signed" and signed["resolved_by"] == "n.sango"
    rejected = state([entry(PROPOSED, record=BASE),
                      entry(REJECTED, actor="n.sango", detail="wrong pay group")])[0]
    assert rejected["status"] == "rejected" and rejected["reason"] == "wrong pay group"


def test_a_re_proposal_after_a_rejection_is_pending_again_and_the_rejection_stays_on_the_chain():
    chain = [entry(PROPOSED, record=BASE), entry(REJECTED, actor="n.sango", detail="no"),
             entry(PROPOSED, record={**BASE, "intent": {"externalCode": "BASIC", "name": "Base"}})]
    rows = state(chain)
    assert len(rows) == 1 and rows[0]["status"] == "pending"
    assert rows[0]["record"]["intent"]["name"] == "Base"
    assert sum(1 for e in chain if e["action"] == REJECTED) == 1


def test_a_resolution_with_no_proposal_before_it_is_ignored_rather_than_invented():
    assert state([entry(SIGNED, actor="n.sango")]) == []
